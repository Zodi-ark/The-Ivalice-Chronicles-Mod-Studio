"""
The texture tree, as a model.

The real unpacked game has **10,011** `.tga`/`.tex` files across 196
directories, and the Sounds tab's tree is larger still at 14,545. That is
the scale this has to hold without the interface thinking about it.

A `QTreeView` over a model only ever asks for the rows it is about to draw,
so the cost is the visible page rather than the tree. Nothing here builds a
widget per file, and nothing flattens the tree to make it easier - a
flattened 10,011-row list would lose the folder structure that is the only
thing making a texture findable by eye.

The model wraps `texture_data.TextureTreeNode` directly rather than copying
it into a shape of its own. The engine decides what the tree is; a second
opinion living in the interface is how the two drift apart.
"""
from __future__ import annotations

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont

from ... import constants as c

# One column.
#
# There were two, "File" and "Status", and Status held the word "replaced".
# It was dead weight in three separate ways: the row is already green and
# bold when it is replaced, so the word repeated what the colour said; the
# folder rows had nothing to put in it at all; and because it was the last
# column the view stretched it to fill, which on a 2560px monitor left
# roughly 1100px of empty column between the file names and the right-hand
# pane. Zodi found that as "tons of empty space in the middle" and the empty
# Status column was the whole of it.
COLUMNS = ("File",)


class TextureTreeModel(QAbstractItemModel):
    def __init__(self, root=None, edits: dict | None = None, parent=None):
        super().__init__(parent)
        self._root = root
        self._edits = edits if edits is not None else {}
        # Qt hands back a raw pointer for each index, so every node has to
        # stay referenced on the Python side or it is collected while the
        # view still holds an index to it.
        self._parents: dict[int, object] = {}
        self._index_nodes: list = []
        # folder id -> replaced files under it; see `_replaced_under`
        self._counts: dict[int, int] = {}

    # -- population ----------------------------------------------------------

    def set_root(self, root) -> None:
        self.beginResetModel()
        try:
            self._root = root
            self._parents = {}
            self._index_nodes = []
            self._counts = {}
            if root is not None:
                self._record(root, None)
        finally:
            self.endResetModel()

    def _record(self, node, parent) -> None:
        self._parents[id(node)] = parent
        self._index_nodes.append(node)
        for child in getattr(node, "children", ()) or ():
            self._record(child, node)

    def _replaced_under(self, node) -> int:
        """
        How many replaced files sit anywhere under a folder.

        Cached per refresh. `data()` is called for every visible row on
        every repaint, and walking a subtree of several thousand files each
        time would make scrolling the `bg/` branch visibly stutter. The
        cache is cleared whenever the edits or the root change, which are
        the only two things that can alter the answer.
        """
        key = id(node)
        cached = self._counts.get(key)
        if cached is not None:
            return cached
        if getattr(node, "is_file", False):
            total = 1 if node.relative_path in self._edits else 0
        else:
            total = sum(self._replaced_under(child)
                        for child in (getattr(node, "children", ()) or ()))
        self._counts[key] = total
        return total

    def set_edits(self, edits: dict, changed_path: str | None = None) -> None:
        """
        Replacement map changed - recolour the rows and recount folders.

        `changed_path` names the one file that moved, when the caller knows
        it. That matters because this is a TREE: `dataChanged` over the
        top-level rows does not repaint their children, and a replaced file
        eight folders deep would keep its old colour while every folder
        above it kept its old count. Emitting up the ancestor chain repaints
        exactly the rows whose displayed text or colour actually changed.

        Without a path - opening a mod recovers hundreds of replacements at
        once - it falls back to resetting the model. That collapses the
        tree, which is acceptable for a bulk change and wrong for a single
        one, which is why the two cases are distinguished at all.
        """
        self._edits = edits
        self._counts = {}
        if self._root is None:
            return
        if changed_path:
            roles = [Qt.DisplayRole, Qt.FontRole, Qt.BackgroundRole,
                     Qt.ForegroundRole]
            index = self.index_for_path(changed_path)
            while index.isValid():
                self.dataChanged.emit(index, index, roles)
                index = self.parent(index)
            return
        self.beginResetModel()
        self.endResetModel()

    # -- tree navigation ------------------------------------------------------

    def _children(self, node) -> list:
        """
        The rows under a node - and at the top, the ROOT'S children.

        The root is the unpacked-game folder itself, and showing it meant
        every session started one click away from anything useful: a single
        row reading `UnpackedGame`, which has to be expanded before `bg`,
        `char`, `ui` and the rest appear. The Tkinter page iterates
        `root.children` and so never draws that row.

        The root object is still held, because `parent()` walks back through
        it and the model needs it to answer for the top level.
        """
        if node is None:
            if self._root is None:
                return []
            return list(getattr(self._root, "children", ()) or [])
        return list(getattr(node, "children", ()) or [])

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        node = parent.internalPointer() if parent.isValid() else None
        children = self._children(node)
        if row >= len(children):
            return QModelIndex()
        return self.createIndex(row, column, children[row])

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        node = index.internalPointer()
        parent = self._parents.get(id(node))
        # A child of the root IS the top level now, so it has no parent as
        # far as the view is concerned. Returning the root here would point
        # the view at a row that is never drawn.
        if parent is None or parent is self._root:
            return QModelIndex()
        grandparent = self._parents.get(id(parent))
        siblings = self._children(grandparent)
        try:
            row = siblings.index(parent)
        except ValueError:
            return QModelIndex()
        return self.createIndex(row, 0, parent)

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.column() > 0:
            return 0
        node = parent.internalPointer() if parent.isValid() else None
        if node is not None and getattr(node, "is_file", False):
            return 0
        return len(self._children(node))

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    # -- data ------------------------------------------------------------------

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        node = index.internalPointer()
        is_file = getattr(node, "is_file", False)
        replaced = is_file and node.relative_path in self._edits

        if role == Qt.DisplayRole:
            if is_file:
                return node.name
            # "textures (12 replaced)" on the folder, so a collapsed branch
            # says whether there is anything of yours inside it. Without it,
            # finding your own work in a 10,011-file tree means opening
            # folders until you hit one - and the Tkinter tab has always
            # labelled them this way (`_count_edited_under`).
            count = self._replaced_under(node)
            return f"{node.name}  ({count} replaced)" if count else node.name
        if role == Qt.FontRole and replaced:
            font = QFont()
            font.setBold(True)
            return font
        # The whole row goes green, the same two colours `mark_edited` puts
        # on every other tab's list rows and the same two the Tkinter trees
        # use. This model set bold and nothing else, so a replaced texture
        # looked almost exactly like an unreplaced one - and bold is not
        # something you can scan for while scrolling past ten thousand rows,
        # which is the entire reason for marking them.
        if role == Qt.BackgroundRole and replaced:
            return QBrush(QColor(c.EDITED_ROW_BG))
        if role == Qt.ForegroundRole and replaced:
            return QBrush(QColor(c.EDITED_ROW_FG))
        if role == Qt.UserRole:
            # What the filter matches on: the whole path, so typing part of
            # a folder name finds the files inside it.
            return node.relative_path
        if role == Qt.UserRole + 1:
            return node
        if role == Qt.UserRole + 2:
            # `widgets.marked_tree.MARKED_ROLE`. The BackgroundRole above
            # only reaches the ITEM, which in a tree begins after the
            # indentation - so the green bar started partway across the
            # row. The view fills the whole row itself and needs to be
            # told which rows those are, without inferring it from a
            # colour it happens to recognise.
            return replaced
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    # -- helpers ---------------------------------------------------------------

    def index_for_path(self, relative_path: str):
        """
        The model index for a texture's relative path, or an invalid one.

        Exists so a jump from another tab - Items' two icon slots, and
        Abilities' icon - can land on the actual file rather than merely
        opening the Textures tab and leaving the reader to find it among ten
        thousand entries. A jump that changes the tab and nothing else is
        the sort of thing that reads as the button being broken.

        Walks down from the root by path segment rather than searching every
        node, so it costs the depth of the path and not the size of the
        tree.
        """
        if self._root is None or not relative_path:
            return QModelIndex()
        wanted = str(relative_path).replace("\\", "/").strip("/")
        parent_index = QModelIndex()
        node = None
        for segment in wanted.split("/"):
            children = self._children(node)
            for row, child in enumerate(children):
                if child.name == segment:
                    parent_index = self.createIndex(row, 0, child)
                    node = child
                    break
            else:
                return QModelIndex()
        return parent_index

    def node_at(self, index):
        source = index
        if hasattr(index, "model") and index.model() is not self:
            source = index.model().mapToSource(index)
        return source.internalPointer() if source.isValid() else None

    def file_count(self) -> int:
        return sum(1 for n in self._index_nodes if getattr(n, "is_file", False))
