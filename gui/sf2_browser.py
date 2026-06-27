"""
gui/sf2_browser.py — Sidebar derecho: gestiona varios SF2 cargados.
Permite importar varios SoundFonts y elegir instrumentos de cualquiera.
"""
import tkinter as tk
from tkinter import ttk, filedialog
import os


class SF2Browser(tk.Frame):
    """Panel derecho con lista de SF2 cargados e instrumentos disponibles."""

    def __init__(self, parent, on_instrument_pick=None, on_sf2_load=None, **kwargs):
        super().__init__(parent, bg='#16213e', **kwargs)
        self.on_instrument_pick = on_instrument_pick
        self.on_sf2_load = on_sf2_load

        # Estado: {sf2_path: {'name': ..., 'samples': dict, 'programs': dict, 'program_list': list}}
        self.loaded_sf2s = {}

        # Header
        tk.Label(self, text="SOUNDFONTS", fg='#8888aa', bg='#16213e',
                 font=('Helvetica', 10, 'bold')).pack(pady=(10, 5))

        # Boton cargar
        btn_frame = tk.Frame(self, bg='#16213e')
        btn_frame.pack(fill=tk.X, padx=5)
        tk.Button(btn_frame, text="+ Cargar SF2", command=self._load_sf2,
                  bg='#0f3460', fg='white', bd=0, padx=10,
                  font=('Helvetica', 8, 'bold')).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Lista de SF2 cargados
        self.sf2_listbox = tk.Listbox(self, bg='#0f3460', fg='white',
                                       selectbackground='#4d96ff',
                                       font=('Helvetica', 8), height=4)
        self.sf2_listbox.pack(fill=tk.X, padx=5, pady=5)
        self.sf2_listbox.bind('<<ListboxSelect>>', self._on_sf2_select)

        # Boton quitar SF2
        tk.Button(self, text="Quitar SF2 seleccionado", command=self._remove_sf2,
                  bg='#0f3460', fg='#ff6b6b', bd=0, padx=10,
                  font=('Helvetica', 7)).pack(fill=tk.X, padx=5)

        # Separador
        sep = tk.Frame(self, height=1, bg='#0f3460')
        sep.pack(fill=tk.X, padx=5, pady=8)

        # Lista de instrumentos del SF2 seleccionado
        tk.Label(self, text="INSTRUMENTOS", fg='#8888aa', bg='#16213e',
                 font=('Helvetica', 10, 'bold')).pack(pady=(0, 5))

        # Search
        search_frame = tk.Frame(self, bg='#16213e')
        search_frame.pack(fill=tk.X, padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *a: self._refresh_instruments())
        tk.Entry(search_frame, textvariable=self.search_var, bg='#0f3460', fg='white',
                 insertbackground='white', font=('Helvetica', 8),
                 relief=tk.FLAT).pack(fill=tk.X)

        # Lista de instrumentos
        inst_frame = tk.Frame(self, bg='#16213e')
        inst_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar = ttk.Scrollbar(inst_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.inst_listbox = tk.Listbox(
            inst_frame, bg='#0f3460', fg='white',
            selectbackground='#6bcb77',
            font=('Helvetica', 8), yscrollcommand=scrollbar.set
        )
        self.inst_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.inst_listbox.yview)
        self.inst_listbox.bind('<Double-Button-1>', self._on_inst_pick)
        self.inst_listbox.bind('<Return>', self._on_inst_pick)

        # Boton "Asignar a pista seleccionada"
        tk.Button(self, text="→ Asignar a pista seleccionada",
                  command=self._on_inst_pick_click,
                  bg='#6bcb77', fg='white', bd=0, padx=10, pady=4,
                  font=('Helvetica', 8, 'bold')).pack(fill=tk.X, padx=5, pady=5)

        # Status
        self.status_label = tk.Label(self, text="Carga un SF2 para empezar",
                                      fg='#666', bg='#16213e',
                                      font=('Helvetica', 7), wraplength=200, justify=tk.LEFT)
        self.status_label.pack(fill=tk.X, padx=5, pady=5)

    # ─── API publica ───

    def load_sf2(self, path):
        """Carga un SF2 y actualiza las listas."""
        try:
            from core import sf2_parser
            name = os.path.basename(path).replace('.sf2', '').replace('.SF2', '')
            samples = sf2_parser.parse(path, max_samples=128)
            programs = sf2_parser.extract_instrument_programs(path)
            program_list = sf2_parser.get_program_list(path)

            self.loaded_sf2s[path] = {
                'name': name,
                'samples': samples,
                'programs': programs,
                'program_list': program_list,
            }

            # Agregar a listbox
            self.sf2_listbox.insert(tk.END, f"{name}  ({len(samples)} smp)")

            # Refrescar instrumentos
            if len(self.sf2_listbox.curselection()) == 0:
                self.sf2_listbox.selection_set(0)
                self._on_sf2_select()

            self.status_label.config(text=f"✅ {name}: {len(samples)} samples, "
                                           f"{len(programs)} programs mapeados")

            if self.on_sf2_load:
                self.on_sf2_load(path, name, samples, programs, program_list)

            return True
        except Exception as e:
            self.status_label.config(text=f"❌ Error: {e}")
            return False

    def get_active_sf2(self):
        """Retorna el SF2 actualmente seleccionado."""
        sel = self.sf2_listbox.curselection()
        if not sel:
            return None
        idx = sel[0]
        paths = list(self.loaded_sf2s.keys())
        if idx >= len(paths):
            return None
        path = paths[idx]
        return path, self.loaded_sf2s[path]

    def get_selected_instrument(self):
        """Retorna (sf2_path, sample_index, program, name) del instrumento seleccionado."""
        sf2_info = self.get_active_sf2()
        if not sf2_info:
            return None
        sf2_path, sf2 = sf2_info
        sel = self.inst_listbox.curselection()
        if not sel:
            return None
        idx = sel[0]
        # idx corresponde a la lista filtrada
        programs = sf2.get('program_list', [])
        query = self.search_var.get().lower().strip()
        if query:
            filtered = [p for p in programs if query in p[1].lower()]
        else:
            filtered = programs
        if idx >= len(filtered):
            return None
        program, label = filtered[idx]
        sample_idx = sf2['programs'].get(program)
        if sample_idx is None:
            return None
        return sf2_path, sample_idx, program, label

    # ─── Callbacks internos ───

    def _load_sf2(self):
        path = filedialog.askopenfilename(
            title="Cargar SoundFont",
            filetypes=[("SoundFont", "*.sf2"), ("All files", "*.*")]
        )
        if path:
            self.load_sf2(path)

    def _remove_sf2(self):
        sel = self.sf2_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        paths = list(self.loaded_sf2s.keys())
        if idx >= len(paths):
            return
        path = paths[idx]
        del self.loaded_sf2s[path]
        self.sf2_listbox.delete(idx)
        self._refresh_instruments()
        self.status_label.config(text=f"🗑️ {os.path.basename(path)} removido")

    def _on_sf2_select(self, event=None):
        self._refresh_instruments()

    def _refresh_instruments(self):
        self.inst_listbox.delete(0, tk.END)
        sf2_info = self.get_active_sf2()
        if not sf2_info:
            return
        _, sf2 = sf2_info
        query = self.search_var.get().lower().strip()
        for program, label in sf2.get('program_list', []):
            if query and query not in label.lower():
                continue
            self.inst_listbox.insert(tk.END, label)

    def _on_inst_pick(self, event=None):
        self._notify_pick()

    def _on_inst_pick_click(self):
        self._notify_pick()

    def _notify_pick(self):
        info = self.get_selected_instrument()
        if info and self.on_instrument_pick:
            sf2_path, sample_idx, program, name = info
            self.on_instrument_pick(sf2_path, sample_idx, program, name)
