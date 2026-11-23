"""
gui/deps_dialog.py — Diálogo de gestión de dependencias.

Muestra el estado de cada herramienta (mido, fluidsynth, ffmpeg, smconv) y
permite instalar las que falten desde la propia interfaz.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading, webbrowser, queue

from core import deps

# Etiquetas legibles por herramienta
TOOL_LABELS = {
    'mido': 'mido (MIDI)',
    'fluidsynth': 'FluidSynth (preview)',
    'ffmpeg': 'FFmpeg / ffplay (audio)',
    'smconv': 'smconv (IT → .bnk SNES)',
}


class DepsDialog(tk.Toplevel):
    """Ventana modal para revisar e instalar dependencias."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Herramientas")
        self.configure(bg='#0b1020')
        self.geometry("760x500")
        self.transient(parent)
        self._rows = {}
        self._busy = False
        self._ui_queue = queue.Queue()

        tk.Label(self, text="Herramientas", fg='#f8fafc', bg='#0b1020',
                 font=('Segoe UI', 14, 'bold')).pack(anchor='w', padx=16, pady=(14, 2))
        tk.Label(self,
                 text="Audio: FluidSynth + FFmpeg    ·    SNES: smconv",
                 fg='#94a3b8', bg='#0b1020', font=('Segoe UI', 9)).pack(anchor='w', padx=16)

        self.list_frame = tk.Frame(self, bg='#0b1020')
        self.list_frame.pack(fill=tk.X, padx=12, pady=10)

        # Consola de salida de instalación
        tk.Label(self, text="Actividad", fg='#94a3b8', bg='#0b1020',
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=16)
        out_frame = tk.Frame(self, bg='#0b1020')
        out_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(3, 10))
        self.output = tk.Text(out_frame, bg='#0f1726', fg='#cbd5e1', height=10,
                              font=('Consolas', 9), wrap='word', bd=0,
                              highlightthickness=1, highlightbackground='#263449')
        self.output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(out_frame, command=self.output.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.output.config(yscrollcommand=sb.set, state='disabled')

        bottom = tk.Frame(self, bg='#0b1020')
        bottom.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(bottom, text="Actualizar", command=self._refresh,
                   style='Quiet.TButton').pack(side=tk.LEFT)
        ttk.Button(bottom, text="Cerrar", command=self.destroy,
                   style='Accent.TButton').pack(side=tk.RIGHT)

        self._refresh()
        self.after(50, self._drain_ui_queue)

    def _queue_ui(self, callback, *args):
        self._ui_queue.put((callback, args))

    def _drain_ui_queue(self):
        try:
            while True:
                callback, args = self._ui_queue.get_nowait()
                callback(*args)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(50, self._drain_ui_queue)

    # ─── Render de filas ───────────────────────────────────────────────────

    def _refresh(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self._rows.clear()

        status = deps.check()
        for tool, info in status.items():
            row = tk.Frame(self.list_frame, bg='#182235')
            row.pack(fill=tk.X, pady=3)

            ok = info['ok']
            mark = '✅' if ok else ('❌' if info['required'] else '⚠️')
            tk.Label(row, text=mark, bg='#182235', font=('Segoe UI Emoji', 11),
                     width=3).pack(side=tk.LEFT, padx=(8, 2), pady=7)

            label = TOOL_LABELS.get(tool, tool)
            tk.Label(row, text=label, fg='#f8fafc', bg='#182235',
                     font=('Segoe UI', 9, 'bold'), anchor='w', width=24).pack(side=tk.LEFT)
            state_text = 'Listo' if ok else 'Falta'
            state_color = '#4ade80' if ok else '#fbbf24'
            tk.Label(row, text=state_text, fg=state_color, bg='#182235',
                     font=('Segoe UI', 8), anchor='w', width=8).pack(side=tk.LEFT)

            if ok:
                continue

            # Preferir descarga portátil (sin instalar nada ni tocar el PATH)
            if deps.has_portable(tool):
                ttk.Button(row, text="Descargar (portátil)",
                           style='Accent.TButton',
                           command=lambda t=tool: self._portable(t)).pack(side=tk.RIGHT, padx=6, pady=4)

            if info['kind'] == 'manual':
                ttk.Button(row, text="Instrucciones",
                           style='Quiet.TButton',
                           command=lambda t=tool: self._show_manual(t)).pack(side=tk.RIGHT, padx=6, pady=4)
            else:
                plan = deps.install_plan(tool)
                if plan:
                    ttk.Button(row, text=f"Instalar ({plan[0][0]})",
                               style='Quiet.TButton',
                               command=lambda t=tool: self._install(t)).pack(side=tk.RIGHT, padx=6, pady=4)
                elif not deps.has_portable(tool):
                    ttk.Button(row, text="Cómo instalar",
                               command=lambda t=tool: self._show_manual(t)).pack(side=tk.RIGHT, padx=6)

    # ─── Acciones ──────────────────────────────────────────────────────────

    def _show_manual(self, tool):
        hint = deps.manual_hint(tool)
        if tool == 'smconv':
            if messagebox.askyesno("Instalación manual",
                                   hint + "\n\n¿Abrir la página de descargas?"):
                webbrowser.open(deps.PVSNESLIB_RELEASES)
        else:
            messagebox.showinfo("Instalación manual", hint)

    def _log(self, line):
        self.output.config(state='normal')
        self.output.insert(tk.END, line + '\n')
        self.output.see(tk.END)
        self.output.config(state='disabled')

    def _install(self, tool):
        if self._busy:
            messagebox.showwarning("Ocupado", "Ya hay una instalación en curso.")
            return
        plan = deps.install_plan(tool)
        if not plan:
            self._show_manual(tool)
            return

        self._busy = True
        self._log(f"\n=== Instalando {tool} ===")

        def worker():
            status = 'fail'
            for label, cmd in plan:
                self._queue_ui(self._log, f"$ {' '.join(cmd)}")
                rc, out = deps.run_install(cmd, on_line=lambda line: self._queue_ui(self._log, line))
                status = deps.classify_result(rc, out)
                if status in ('ok', 'already'):
                    break
                self._queue_ui(self._log, f"[{label}] falló (código {rc}), probando alternativa...")
            self._queue_ui(self._finish_install, tool, status)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_install(self, tool, status):
        self._busy = False
        if status == 'ok':
            self._log(f"✅ {tool} instalado.")
            self._restart_hint(tool)
        elif status == 'already':
            self._log(f"ℹ️ {tool} ya estaba instalado.")
            self._restart_hint(tool, already=True)
        else:
            self._log(f"❌ No se pudo instalar {tool} automáticamente.")
            messagebox.showwarning(
                "Instalación fallida",
                f"No se pudo instalar {tool}.\n\n{deps.manual_hint(tool)}")
        self._refresh()
        if hasattr(self.master, '_refresh_dependency_status'):
            self.master._refresh_dependency_status()

    def _restart_hint(self, tool, already=False):
        """Avisa que hace falta reiniciar para detectar la herramienta (PATH/pip)."""
        pre = f"{tool} ya estaba instalado." if already else f"{tool} se instaló."
        if tool == 'mido':
            extra = "Reinicia midi2it para usarlo."
        else:
            extra = ("Si la app no lo detecta aún, cierra y vuelve a abrir midi2it "
                     "(el PATH se actualiza al reiniciar).")
        messagebox.showinfo("Reinicio recomendado", f"{pre}\n\n{extra}")

    # ─── Descarga portátil (sin instalar, sin tocar el PATH) ─────────────────

    def _portable(self, tool):
        if self._busy:
            messagebox.showwarning("Ocupado", "Ya hay una descarga en curso.")
            return
        self._busy = True
        self._log(f"\n=== Descargando {tool} (portátil) ===")

        def worker():
            status, path = deps.portable_install(
                tool, on_line=lambda line: self._queue_ui(self._log, line))
            self._queue_ui(self._finish_portable, tool, status)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_portable(self, tool, status):
        self._busy = False
        if status == 'ok':
            self._log(f"✅ {tool} descargado y listo (portátil).")
            messagebox.showinfo(
                "Listo",
                f"{tool} quedó listo para usar (sin reiniciar).\n\n"
                f"Ubicación: {deps.tools_dir()}")
        else:
            self._log(f"❌ No se pudo descargar {tool}.")
            messagebox.showwarning(
                "Descarga fallida",
                f"No se pudo obtener {tool} de forma portátil.\n\n{deps.manual_hint(tool)}")
        self._refresh()
        if hasattr(self.master, '_refresh_dependency_status'):
            self.master._refresh_dependency_status()
