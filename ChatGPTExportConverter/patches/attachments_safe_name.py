# Replacement for attachments.safe_name() in the frozen program (1.2.4).
# Only this function's code object is swapped; it keeps the module's globals (re) and its
# default limit=120. Adds: Windows reserved device names (CON, NUL, COM1, ...) get a "_" prefix,
# and trailing dots/spaces left by truncation are removed (Windows drops them silently).
def safe_name(s, limit=120):
    s = re.sub('[<>:"/\\\\|?*\\x00-\\x1f]', '_', s or '').strip(' .')
    s = s[:limit].rstrip(' .')
    if s.split('.')[0].rstrip(' ').upper() in {
            'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$',
            'COM0', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT0', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9',
            'COM¹', 'COM²', 'COM³', 'LPT¹', 'LPT²', 'LPT³'}:
        s = '_' + s
    return s or 'file'
