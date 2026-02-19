from config import MAX_MESSAGE_LENGTH

INCLUDED_SECTIONS={
    'agent updates',
    'competitive updates',
    'map updates',
}

def filter_sections(text):
    """
    Filters the patch notes text to only include specified sections and the TLDR paragraph

    """

    lines = text.split('\n')
    filtered_lines = []
    include_current = True

    for line in lines:
        stripped = line.strip()

        # Check for section headers
        if stripped and stripped.isupper() and len(stripped) <50:
            section_lower = stripped.lower()

            include_current = section_lower in INCLUDED_SECTIONS

        # Add a line if we are in an included section
        if include_current:
            filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)



def smart_chunk(text, max_length=MAX_MESSAGE_LENGTH):
    """Split text at natural break points while staying under Discord's limit."""

    # Apply markdown formatting line by line, preserving order
    lines = text.split('\n')
    formatted_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            formatted_lines.append('')
        # Main headers (ALL CAPS like "BUG FIXES", "AGENTS")
        elif stripped.isupper() and len(stripped) < 50:
            formatted_lines.append(f'\n__**{stripped}**__')
        # Sub-headers (short title-case lines like "Harbor", "Fade", "General")
        elif len(stripped) < 30 and stripped.istitle() and not stripped.startswith('Fixed'):
            formatted_lines.append(f'\n**{stripped}**')
        # Bug fix lines - format as bullet points
        elif stripped.startswith('Fixed'):
            formatted_lines.append(f'• {stripped}')
        # Other bullet-point style lines
        elif stripped.startswith(('-', '•', '*')):
            formatted_lines.append(f'• {stripped[1:].strip()}')
        else:
            formatted_lines.append(stripped)

    formatted_text = '\n'.join(formatted_lines)

    # Smart chunking - split at section breaks (double newlines or before headers)
    chunks = []
    current_chunk = ''

    for line in formatted_text.split('\n'):
        # Check if adding this line exceeds the limit
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line
        else:
            # Start new chunk before major headers to keep sections together
            if line.startswith('__**') and len(current_chunk) > 500:
                chunks.append(current_chunk.strip())
                current_chunk = line
            else:
                current_chunk += '\n' + line if current_chunk else line

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks
