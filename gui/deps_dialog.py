"""
gui/deps_dialog.py — Diálogo de gestión de dependencias.

Muestra el estado de cada herramienta (mido, fluidsynth, ffmpeg, smconv) y
permite instalar las que falten desde la propia interfaz.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading, webbrowser

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
        self.title("Dependencias — midi2it")
        self.configure(bg='#1a1a2e')
        self.geometry("640x460")
        self.transient(parent)
        self._rows = {}
        self._busy = False

        tk.Label(self, text="Estado de dependencias", fg='white', bg='#1a1a2e',
                 font=('Helvetica', 12, 'bold')).pack(pady=(12, 4))
        tk.Label(self,
                 text="Las herramientas opcionales mejoran preview y exportación a SNES.",
                 fg='#8888aa', bg='#1a1a2e', font=('Helvetica', 8)).pack()

        self.list_frame = tk.Frame(self, bg='#1a1a2e')
        self.list_frame.pack(fill=tk.X, padx=12, pady=8)

        # Consola de salida de instalación
        tk.Label(self, text="Salida:", fg='#8888aa', bg='#1a1a2e',
                 font=('Helvetica', 8)).pack(anchor='w', padx=12)
        out_frame = tk.Frame(self, bg='#1a1a2e')
        out_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        self.output = tk.Text(out_frame, bg='#0d0d1a', fg='#9ad', height=10,
                              font=('Courier', 8), wrap='word', bd=0)
        self.output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(out_frame, command=self.output.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.output.config(yscrollcommand=sb.set, state='disabled')

        bottom = tk.Frame(self, bg='#1a1a2e')
        bottom.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(bottom, text="Refrescar", command=self._refresh).pack(side=tk.LEFT)
        ttk.Button(bottom, text="Cerrar", command=self.destroy).pack(side=tk.RIGHT)

        self._refresh()

    # ─── Render de filas ───────────────────────────────────────────────────

    def _refresh(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self._rows.clear()

        status = deps.check()
        for tool, info in status.items():
            row = tk.Frame(self.list_frame, bg='#16213e')
            row.pack(fill=tk.X, pady=2)

            ok = info['ok']
            mark = '✅' if ok else ('❌' if info['required'] else '⚠️')
            tk.Label(row, text=mark, bg='#16213e', font=('Helvetica', 11),
                     width=3).pack(side=tk.LEFT)

            label = TOOL_LABELS.get(tool, tool)
            req = ' (requerida)' if info['required'] else ' (opcional)'
            tk.Label(row, text=label + req, fg='white', bg='#16213e',
                     font=('Helvetica', 9, 'bold'), anchor='w', width=26).pack(side=tk.LEFT)
            tk.Label(row, text=info['desc'], fg='#8888aa', bg='#16213e',
                     font=('Helvetica', 8), anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True)

            if ok:
                tk.Label(row, text="instalado", fg='#6bcb77', bg='#16213e',
                         font=('Helvetica', 8)).pack(side=tk.RIGHT, padx=6)
                continue

            if info['kind'] == 'manual':
                ttk.Button(row, text="Instrucciones",
                           command=lambda t=tool: self._show_manual(t)).pack(side=tk.RIGHT, padx=6)
            else:
                plan = deps.install_plan(tool)
                if plan:
                    ttk.Button(row, text=f"Instalar ({plan[0][0]})",
                               command=lambda t=tool: self._install(t)).pack(side=tk.RIGHT, padx=6)
                else:
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
                self._log(f"$ {' '.join(cmd)}")
                rc, out = deps.run_install(cmd, on_line=lambda l: self.after(0, self._log, l))
                status = deps.classify_result(rc, out)
                if status in ('ok', 'already'):
                    break
                self._log(f"[{label}] falló (código {rc}), probando alternativa...")
            self.after(0, self._finish_install, tool, status)

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

    def _restart_hint(self, tool, already=False):
        """Avisa que hace falta reiniciar para detectar la herramienta (PATH/pip)."""
        pre = f"{tool} ya estaba instalado." if already else f"{tool} se instaló."
        if tool == 'mido':
            extra = "Reinicia midi2it para usarlo."
        else:
            extra = ("Si la app no lo detecta aún, cierra y vuelve a abrir midi2it "
                     "(el PATH se actualiza al reiniciar).")
        messagebox.showinfo("Reinicio recomendado", f"{pre}\n\n{extra}")
