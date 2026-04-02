import re
from config.config import MAX_MESSAGE_LENGTH
from bs4 import BeautifulSoup, NavigableString, Tag

INCLUDED_SECTIONS = {
    'agent updates',
}

BULLET_CHARS = ['•', '◦']
SECTION_DIVIDER = '──────────────────'

def process_inline(node):
    """ Extract inline text from a node, preserving the bold formatting """

    parts = []

    for child in node.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            if child.name in ('strong', 'b'):
                parts.append(f'**{process_inline(child)}**')
            elif child.name == 'br':
                parts.append('\n')
            else:
                parts.append(process_inline(child))
    return ''.join(parts)

def process_list(list_node, lines, indent=0):
    """ Recursively process a list (ul or ol) and its children, adding formatted lines to the output """
    ordered = list_node.name == 'ol'
    bullet = BULLET_CHARS[min(indent, len(BULLET_CHARS)-1)]
    prefix = '          ' * indent
    counter = 1

    for child in list_node.children:
        if not isinstance(child, Tag) or child.name != 'li':
            continue

        # Separate inline text from every nested lists within this list
        inline_parts = []
        nested_lists = []

        for c in child.children:
            if isinstance(c, Tag) and c.name in ('ul', 'ol'):
                nested_lists.append(c)
            elif isinstance(c, NavigableString):
                inline_parts.append(str(c))
            elif isinstance(c, Tag):
                inline_parts.append(process_inline(c))

        li_text = re.sub(r'\s+', ' ', ''.join(inline_parts)).strip()
        li_text = re.sub(r'(\d[\d.]*)\s*>>>\s*(\d[\d.]*)', r'**\1 → \2**', li_text)

        if ordered:
            lines.append(f'{prefix}{counter}. {li_text}')
            lines.append('') #add extra linebreak after bullet points for easier reading
            counter += 1
        else:
            lines.append(f'{prefix}{bullet} {li_text}')
            lines.append('') #add extra linebreak after bullet points for easier reading

        for nested in nested_lists:
            process_list(nested, lines, indent + 1)

def process_node(node, lines):
    """ Recursively walk HTML nodes and append the Discord-formatted lines """

    for child in node.children: 
        if isinstance(child, NavigableString):
            text = str(child).strip()

            if text:
                lines.append(text)
        elif isinstance(child, Tag):
            name = child.name

            if name in ('h1', 'h2'):
                text = child.get_text(strip=True)
                lines.append('')
                lines.append(f'## {text}')
            elif name in ('h3', 'h4', 'h5'):
                text = child.get_text(strip=True)
                lines.append('')
                lines.append(SECTION_DIVIDER)
                lines.append(f'### {text}')
            elif name == 'p':
                text = re.sub(r'\s+', ' ', process_inline(child)).strip()
                if text:
                    lines.append(text)
            elif name in ('ul', 'ol'):
                process_list(child, lines, indent=0)
            elif name == 'br':
                lines.append('')
            else:
                # div, span, section, article, etc. — recurse
                process_node(child, lines)
            
def html_to_discord_markdown(html):
    """ Convert HTML patch notes to discord markdown """
    soup = BeautifulSoup(html, 'html.parser')
    lines = []
    process_node(soup, lines)
    text = '\n'.join(lines)
    # Collapse 3+ consecutive newlines to 2
    return re.sub(r'\n{3,}', '\n\n', text)

def filter_sections(text):
    """

    Filters the patch notes text to only include specified sections and the TLDR paragraph
    Detects section headers by the ## HEADER format

    """

    lines = text.split('\n')
    filtered_lines = []
    include_current = True

    for line in lines:
        stripped = line.strip()

        # Check for top-level section headers (## Header)
        if stripped.startswith('## '):
            header_text = stripped[3:].strip().lower()
            include_current = header_text in INCLUDED_SECTIONS

        # Add a line if we are in an included section
        if include_current:
            filtered_lines.append(line)

    return '\n'.join(filtered_lines)



def smart_chunk(html_content, max_length=MAX_MESSAGE_LENGTH):
    """Split text at natural break points while staying under Discord's limit."""

    # Call filter_sections to reduce the text to only relevant sections before formatting and chunking
    text = filter_sections(html_to_discord_markdown(html_content))

    chunks = []
    current_chunk = ''

    for line in text.split('\n'):
        # Check if adding this line exceeds the limit
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line
        else:
            # Start a new chunk before major headers to keep sections together
            if line.startswith('## ') and len(current_chunk) > 500:
                chunks.append(current_chunk.strip())
                current_chunk = line
            else:
                current_chunk += '\n' + line if current_chunk else line

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks
