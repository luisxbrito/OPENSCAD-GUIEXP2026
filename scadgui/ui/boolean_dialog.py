"""Diálogo asistente para operaciones booleanas (Restar, Unir, Intersecar).

Proporciona autocompletado para buscar sólidos por nombre y selección
interactiva directamente sobre el árbol de piezas del modelo.
Explica claramente qué sólido es la base y cuáles se le restan, unen o intersectan.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox,
                               QCompleter, QDialog, QDialogButtonBox, QFrame, QGroupBox,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
                               QRadioButton, QSplitter, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from ..catalog import SPECS
from ..i18n import tr
from ..model import Document, Node, RawCode
from .icons import icon


class BooleanDialog(QDialog):
    """Diálogo interactivo para configurar operaciones booleanas con autocompletado y selección en árbol."""

    def __init__(self, doc: Document, initial_kind: str = "difference",
                 selected_ids: Optional[list[int]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle(tr("Asistente de Operaciones Booleanas"))
        self.resize(760, 560)
        self.setMinimumSize(640, 480)

        # Recopilar todos los nodos seleccionables (sólidos)
        self.solids: list[tuple[int, str, str]] = doc.get_solids()
        self.id_to_solid: dict[int, tuple[str, str]] = {sid: (lbl, k) for sid, lbl, k in self.solids}

        # Estado inicial
        self.current_kind = initial_kind if initial_kind in ("difference", "union", "intersection") else "difference"
        self.base_id: Optional[int] = None
        self.target_ids: list[int] = []

        # Determinar selecciones iniciales
        sel = selected_ids or []
        if sel:
            valid_sel = [i for i in sel if i in self.id_to_solid]
            if valid_sel:
                self.base_id = valid_sel[0]
                self.target_ids = [i for i in valid_sel[1:]]
        if self.base_id is None and self.solids:
            self.base_id = self.solids[0][0]
            if len(self.solids) > 1:
                self.target_ids = [self.solids[1][0]]

        self._building_ui = True
        self._build_ui()
        self._building_ui = False
        self._sync_tree_from_state()
        self._update_summary()

    def _build_ui(self) -> None:
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(16, 14, 16, 14)
        main_lay.setSpacing(12)

        # 1. Selector de tipo de operación booleana
        op_box = QGroupBox(tr("Tipo de Operación Booleana"))
        op_lay = QHBoxLayout(op_box)
        op_lay.setSpacing(20)

        self.btn_group = QButtonGroup(self)
        self.rb_diff = QRadioButton(tr("Restar (difference)"))
        self.rb_diff.setIcon(icon("difference", "#B91C1C"))
        self.rb_diff.setToolTip(tr("El primer sólido es la base (+); los demás se le restan (-) como cortes o huecos."))

        self.rb_union = QRadioButton(tr("Unir (union)"))
        self.rb_union.setIcon(icon("union", "#15803D"))
        self.rb_union.setToolTip(tr("Une y fusiona todos los sólidos en un único cuerpo continuo."))

        self.rb_inter = QRadioButton(tr("Intersecar (intersection)"))
        self.rb_inter.setIcon(icon("intersection", "#7E22CE"))
        self.rb_inter.setToolTip(tr("Conserva exclusivamente el volumen común compartido por todos los sólidos."))

        self.btn_group.addButton(self.rb_diff, 1)
        self.btn_group.addButton(self.rb_union, 2)
        self.btn_group.addButton(self.rb_inter, 3)

        if self.current_kind == "difference":
            self.rb_diff.setChecked(True)
        elif self.current_kind == "union":
            self.rb_union.setChecked(True)
        else:
            self.rb_inter.setChecked(True)

        self.rb_diff.toggled.connect(lambda on: self._on_kind_changed("difference") if on else None)
        self.rb_union.toggled.connect(lambda on: self._on_kind_changed("union") if on else None)
        self.rb_inter.toggled.connect(lambda on: self._on_kind_changed("intersection") if on else None)

        op_lay.addWidget(self.rb_diff)
        op_lay.addWidget(self.rb_union)
        op_lay.addWidget(self.rb_inter)
        op_lay.addStretch(1)
        main_lay.addWidget(op_box)

        # 2. Panel central: selector con autocompletado y árbol del modelo
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel izquierdo: controles de autocompletado y selección de roles
        left_panel = QWidget()
        left_lay = QVBoxLayout(left_panel)
        left_lay.setContentsMargins(0, 0, 8, 0)
        left_lay.setSpacing(10)

        # Sección Base (para difference)
        self.base_group = QGroupBox(tr("Sólido Base (al que se le resta)"))
        base_lay = QVBoxLayout(self.base_group)
        base_hint = QLabel(tr("Escribe o autocompleta el nombre del sólido principal (+):"))
        base_hint.setStyleSheet("color: #64748B; font-size: 11px;")
        base_lay.addWidget(base_hint)

        self.combo_base = QComboBox()
        self.combo_base.setEditable(True)
        self.combo_base.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._populate_combo(self.combo_base)
        self.combo_base.currentIndexChanged.connect(self._on_combo_base_changed)
        base_lay.addWidget(self.combo_base)

        btn_swap_lay = QHBoxLayout()
        self.btn_set_base_from_tree = QPushButton(tr("⭐ Usar selección del árbol como Base"))
        self.btn_set_base_from_tree.clicked.connect(self._set_base_from_tree_selection)
        self.btn_swap = QPushButton(tr("⇅ Intercambiar Base y Resta"))
        self.btn_swap.clicked.connect(self._swap_base_and_first_target)
        btn_swap_lay.addWidget(self.btn_set_base_from_tree)
        btn_swap_lay.addWidget(self.btn_swap)
        base_lay.addLayout(btn_swap_lay)
        left_lay.addWidget(self.base_group)

        # Sección Sólidos Secundarios / Restas / Fusión
        self.target_group = QGroupBox(tr("Sólidos que se restan (cortes / huecos)"))
        target_lay = QVBoxLayout(self.target_group)
        self.target_hint = QLabel(tr("Busca por nombre con autocompletado o márcalos en el árbol:"))
        self.target_hint.setStyleSheet("color: #64748B; font-size: 11px;")
        target_lay.addWidget(self.target_hint)

        add_row = QHBoxLayout()
        self.combo_add_target = QComboBox()
        self.combo_add_target.setEditable(True)
        self.combo_add_target.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._populate_combo(self.combo_add_target)
        self.btn_add_target = QPushButton(tr("+ Añadir a la operación"))
        self.btn_add_target.clicked.connect(self._on_add_target_clicked)
        add_row.addWidget(self.combo_add_target, 1)
        add_row.addWidget(self.btn_add_target)
        target_lay.addLayout(add_row)

        self.lbl_selected_targets = QLabel(tr("Piezas marcadas: ninguna"))
        self.lbl_selected_targets.setStyleSheet("font-weight: bold; color: #1E293B; margin-top: 4px;")
        target_lay.addWidget(self.lbl_selected_targets)
        target_lay.addStretch(1)
        left_lay.addWidget(self.target_group, 1)

        splitter.addWidget(left_panel)

        # Panel derecho: Árbol del modelo interactivo
        right_panel = QWidget()
        right_lay = QVBoxLayout(right_panel)
        right_lay.setContentsMargins(8, 0, 0, 0)
        right_lay.setSpacing(6)

        tree_title = QLabel(tr("Árbol del Modelo (selecciona o marca con casillas):"))
        tree_title.setStyleSheet("font-weight: 600; color: #1E293B;")
        right_lay.addWidget(tree_title)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("Pieza / Sólido"), tr("Rol Booleano")])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.itemChanged.connect(self._on_tree_item_changed)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        self._populate_tree()
        right_lay.addWidget(self.tree, 1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 5)
        main_lay.addWidget(splitter, 1)

        # 3. Caja de Resumen didáctico explicativo en vivo
        self.summary_box = QFrame()
        self.summary_box.setFrameShape(QFrame.Shape.StyledPanel)
        self.summary_box.setStyleSheet(
            "QFrame { background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 6px; padding: 8px; }"
        )
        sum_lay = QVBoxLayout(self.summary_box)
        sum_lay.setContentsMargins(10, 8, 10, 8)
        sum_lay.setSpacing(4)

        self.sum_title = QLabel()
        self.sum_title.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.sum_desc = QLabel()
        self.sum_desc.setWordWrap(True)
        self.sum_desc.setStyleSheet("color: #334155; font-size: 12px;")
        self.sum_code = QLabel()
        self.sum_code.setStyleSheet("font-family: monospace; font-size: 11px; color: #0F172A; background: #E2E8F0; padding: 4px 6px; border-radius: 4px;")

        sum_lay.addWidget(self.sum_title)
        sum_lay.addWidget(self.sum_desc)
        sum_lay.addWidget(self.sum_code)
        main_lay.addWidget(self.summary_box)

        # 4. Botones de acción
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Aplicar Operación"))
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancelar"))
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        main_lay.addWidget(btn_box)

    def _populate_combo(self, combo: QComboBox) -> None:
        combo.clear()
        names = []
        for sid, label, kind in self.solids:
            display_text = f"{label} ({kind})"
            names.append(display_text)
            combo.addItem(icon(kind, "#1E293B"), display_text, sid)

        # Configurar QCompleter para autocompletado en combo
        completer = QCompleter(names, combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        combo.setCompleter(completer)

    def _populate_tree(self) -> None:
        self.tree.clear()
        node_map = {}

        def add_node(n, parent_item):
            item = QTreeWidgetItem(parent_item)
            item.setData(0, Qt.ItemDataRole.UserRole, n.id)
            item.setText(0, n.label)
            if isinstance(n, RawCode):
                item.setIcon(0, icon("lock", "#94A3B8"))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            else:
                item.setIcon(0, icon(n.kind, "#334155"))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
                item.setCheckState(0, Qt.CheckState.Unchecked)
            node_map[n.id] = item
            for child in n.children:
                add_node(child, item)

        for n in self.doc.children:
            add_node(n, self.tree.invisibleRootItem())
        self.tree.expandAll()
        self._tree_items = node_map

    def _on_kind_changed(self, kind: str) -> None:
        self.current_kind = kind
        if kind == "difference":
            self.base_group.setVisible(True)
            self.target_group.setTitle(tr("Sólidos que se restan (cortes / huecos)"))
            self.target_hint.setText(tr("Busca por nombre con autocompletado o márcalos en el árbol:"))
        elif kind == "union":
            self.base_group.setVisible(False)
            self.target_group.setTitle(tr("Sólidos a unir (fusión)"))
            self.target_hint.setText(tr("Selecciona los sólidos que formarán la unión continua:"))
        else:  # intersection
            self.base_group.setVisible(False)
            self.target_group.setTitle(tr("Sólidos a intersecar (volumen común)"))
            self.target_hint.setText(tr("Selecciona los sólidos cuyo volumen común deseas conservar:"))
        self._sync_tree_from_state()
        self._update_summary()

    def _on_combo_base_changed(self, index: int) -> None:
        if self._building_ui:
            return
        sid = self.combo_base.currentData()
        if sid is not None and sid != self.base_id:
            self.base_id = sid
            # Si estaba en las restas, sacarlo
            if sid in self.target_ids:
                self.target_ids.remove(sid)
            self._sync_tree_from_state()
            self._update_summary()

    def _set_base_from_tree_selection(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        nid = items[0].data(0, Qt.ItemDataRole.UserRole)
        if nid in self.id_to_solid:
            self.base_id = nid
            if nid in self.target_ids:
                self.target_ids.remove(nid)
            # Actualizar combo
            for i in range(self.combo_base.count()):
                if self.combo_base.itemData(i) == nid:
                    self.combo_base.setCurrentIndex(i)
                    break
            self._sync_tree_from_state()
            self._update_summary()

    def _swap_base_and_first_target(self) -> None:
        if self.base_id is not None and self.target_ids:
            old_base = self.base_id
            new_base = self.target_ids[0]
            self.base_id = new_base
            self.target_ids[0] = old_base
            # Sincronizar combo
            for i in range(self.combo_base.count()):
                if self.combo_base.itemData(i) == self.base_id:
                    self.combo_base.setCurrentIndex(i)
                    break
            self._sync_tree_from_state()
            self._update_summary()

    def _on_add_target_clicked(self) -> None:
        sid = self.combo_add_target.currentData()
        if sid is not None and sid not in self.target_ids and sid != self.base_id:
            self.target_ids.append(sid)
            self._sync_tree_from_state()
            self._update_summary()

    def _on_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._building_ui:
            return
        nid = item.data(0, Qt.ItemDataRole.UserRole)
        if nid not in self.id_to_solid:
            return
        is_checked = item.checkState(0) == Qt.CheckState.Checked
        if is_checked:
            if self.current_kind == "difference" and nid == self.base_id:
                # No se puede restar la base a sí misma
                self._building_ui = True
                item.setCheckState(0, Qt.CheckState.Unchecked)
                self._building_ui = False
                return
            if nid not in self.target_ids:
                self.target_ids.append(nid)
        else:
            if nid in self.target_ids:
                self.target_ids.remove(nid)
        self._update_summary()

    def _on_tree_selection_changed(self) -> None:
        items = self.tree.selectedItems()
        self.btn_set_base_from_tree.setEnabled(bool(items and items[0].data(0, Qt.ItemDataRole.UserRole) in self.id_to_solid))

    def _sync_tree_from_state(self) -> None:
        self._building_ui = True
        for nid, item in self._tree_items.items():
            if nid not in self.id_to_solid:
                continue
            if self.current_kind == "difference" and nid == self.base_id:
                item.setText(1, tr("⭐ Base (+) [Minuendo]"))
                item.setCheckState(0, Qt.CheckState.Unchecked)
                item.setForeground(1, QColor("#166534"))
            elif nid in self.target_ids:
                if self.current_kind == "difference":
                    item.setText(1, tr("✂️ Se resta (-) [Sustraendo]"))
                    item.setForeground(1, QColor("#991B1B"))
                elif self.current_kind == "union":
                    item.setText(1, tr("➕ Se une (∪)"))
                    item.setForeground(1, QColor("#15803D"))
                else:
                    item.setText(1, tr("🔍 Intersección (∩)"))
                    item.setForeground(1, QColor("#6B21A8"))
                item.setCheckState(0, Qt.CheckState.Checked)
            else:
                item.setText(1, "")
                item.setCheckState(0, Qt.CheckState.Unchecked)
                item.setForeground(1, QColor("#64748B"))

        # Seleccionar base en combo
        if self.base_id is not None:
            for i in range(self.combo_base.count()):
                if self.combo_base.itemData(i) == self.base_id:
                    self.combo_base.setCurrentIndex(i)
                    break

        self._building_ui = False

    def _update_summary(self) -> None:
        base_name = self.id_to_solid.get(self.base_id, (tr("Ninguna"), ""))[0] if self.base_id else tr("Ninguna")
        target_names = [self.id_to_solid.get(tid, (f"ID {tid}", ""))[0] for tid in self.target_ids]

        # Actualizar texto de seleccionados
        if self.target_ids:
            self.lbl_selected_targets.setText(f"{tr('Piezas marcadas')}: {', '.join(target_names)}")
        else:
            self.lbl_selected_targets.setText(tr("Piezas marcadas: ninguna"))

        if self.current_kind == "difference":
            self.sum_title.setText(f"✂️ {tr('Restar')}: {base_name} − {', '.join(target_names) if target_names else tr('(sin cortes)')}")
            self.sum_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #991B1B;")
            if target_names:
                self.sum_desc.setText(
                    f"{tr('El sólido base')} <b>{base_name}</b> {tr('permanecerá y se le sustraerán los volúmenes de')} "
                    f"<b>{', '.join(target_names)}</b>."
                )
            else:
                self.sum_desc.setText(tr("Marca al menos un sólido en el árbol o combo para restarlo de la Base."))
            cuts_code = "; ".join(target_names) + ";" if target_names else "// ..."
            self.sum_code.setText(f"difference() {{\n    {base_name}(); // Base (+)\n    {cuts_code} // Restas (-)\n}}")

        elif self.current_kind == "union":
            all_names = []
            if self.base_id is not None and self.base_id not in self.target_ids:
                all_names.append(base_name)
            all_names.extend(target_names)
            names_str = " ∪ ".join(all_names) if all_names else tr("(ninguno)")
            self.sum_title.setText(f"➕ {tr('Unir')}: {names_str}")
            self.sum_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #15803D;")
            self.sum_desc.setText(
                f"{tr('Todos los sólidos seleccionados')} (<b>{', '.join(all_names)}</b>) "
                f"{tr('se fusionarán en un único cuerpo sólido sin huecos interiores.')}"
            )
            items_code = "; ".join(all_names) + ";" if all_names else "// ..."
            self.sum_code.setText(f"union() {{\n    {items_code}\n}}")

        else:  # intersection
            all_names = []
            if self.base_id is not None and self.base_id not in self.target_ids:
                all_names.append(base_name)
            all_names.extend(target_names)
            names_str = " ∩ ".join(all_names) if all_names else tr("(ninguno)")
            self.sum_title.setText(f"🔍 {tr('Intersecar')}: {names_str}")
            self.sum_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #6B21A8;")
            self.sum_desc.setText(
                f"{tr('Se conservará exclusivamente el material donde coincidan simultáneamente')} "
                f"<b>{', '.join(all_names)}</b>."
            )
            items_code = "; ".join(all_names) + ";" if all_names else "// ..."
            self.sum_code.setText(f"intersection() {{\n    {items_code}\n}}")

    def get_result(self) -> dict:
        """Devuelve la configuración lista para aplicar la operación booleana."""
        if self.current_kind == "difference":
            ordered_ids = []
            if self.base_id is not None:
                ordered_ids.append(self.base_id)
            for tid in self.target_ids:
                if tid not in ordered_ids:
                    ordered_ids.append(tid)
            return {
                "kind": "difference",
                "base_id": self.base_id,
                "other_ids": self.target_ids,
                "ordered_ids": ordered_ids,
            }
        else:
            all_ids = []
            if self.base_id is not None and self.base_id not in all_ids:
                all_ids.append(self.base_id)
            for tid in self.target_ids:
                if tid not in all_ids:
                    all_ids.append(tid)
            return {
                "kind": self.current_kind,
                "base_id": None,
                "other_ids": all_ids,
                "ordered_ids": all_ids,
            }
