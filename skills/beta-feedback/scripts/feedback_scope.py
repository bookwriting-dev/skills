"""Resolve a reader's stated scope against the chapter order in a frozen beta edition."""
from pathlib import Path


def matches(section, selector):
    names = (section.get('chapter_id'), section.get('label'), section['path'], Path(section['path']).stem)
    return any(name and name.casefold() == selector.casefold() for name in names)


def resolve(note, edition):
    chapters = [section for section in edition['sections'] if section.get('chapter_id')]

    def index(selector):
        hits = [i for i, section in enumerate(chapters) if matches(section, selector)]
        if len(hits) != 1:
            raise ValueError(f'chapter reference is missing or ambiguous in the reader edition: {selector}')
        return hits[0]

    if 'chapter_range' in note:
        first, last = map(index, note['chapter_range'])
        if last < first:
            raise ValueError('chapter range ends before it starts in the reader edition')
        selected = chapters[first:last + 1]
        kind = 'range'
        label = f"{selected[0]['label']} through {selected[-1]['label']}"
    elif note.get('chapter'):
        selected = [chapters[index(note['chapter'])]]
        kind, label = 'chapter', selected[0]['label']
    else:
        selected = chapters
        kind, label = 'book', 'Whole book'
    if not selected:
        raise ValueError('no narrative chapters in the reader edition')
    return {'kind': kind, 'label': label, 'chapter_ids': [s['chapter_id'] for s in selected]}, selected
