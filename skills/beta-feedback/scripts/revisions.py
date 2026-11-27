"""Read WordprocessingML tracked changes as the text before and after them."""
WORD = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
INSERTED = {WORD + 'ins', WORD + 'moveTo'}
DELETED = {WORD + 'del', WORD + 'moveFrom'}
TEXT = {WORD + tag for tag in ('t', 'delText', 'tab', 'br', 'cr')}


def value(node):
    return (node.text or '') if node.tag in (WORD + 't', WORD + 'delText') else ' '


def walk(node, wrappers=()):
    """Yield descendants in document order with the revision elements that enclose them.

    Paragraph properties hold no reader text, so their subtree is left out.
    """
    for child in node:
        if child.tag == WORD + 'pPr':
            continue
        yield child, wrappers
        inner = wrappers + (child,) if child.tag in INSERTED | DELETED else wrappers
        yield from walk(child, inner)


def in_original(wrappers):
    return not any(item.tag in INSERTED for item in wrappers)


def in_revised(wrappers):
    return not any(item.tag in DELETED for item in wrappers)


def paragraph_mark(paragraph):
    """The tracked insertion or deletion of the paragraph break itself, if any."""
    properties = paragraph.find(f'{WORD}pPr/{WORD}rPr')
    for child in properties if properties is not None else ():
        if child.tag in INSERTED | DELETED:
            return child
    return None
