from ._base import Dummy
class QAction(Dummy): pass
class QColor(Dummy): pass
class QFont(Dummy): pass
class QIcon(Dummy): pass
class QKeySequence(Dummy): pass
class QPainter(Dummy): pass
class QPixmap(Dummy): pass
class QShortcut(Dummy): pass
class QSyntaxHighlighter(Dummy): pass
class QTextCharFormat(Dummy): pass
class QTextCursor(Dummy): pass
class QTextFormat(Dummy): pass
def __getattr__(name): return getattr(Dummy, name)
