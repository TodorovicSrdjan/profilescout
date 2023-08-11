class ConstantsNamespace:
    __slots__ = ()

    # File extension of the screenshot
    IMG_EXT = 'png'

    # Default image resolution
    WIDTH = 2880
    HEIGHT = 1620

    # Time for web driver to wait implicitly before attempting to
    # perform the action
    IMPL_WAIT_FOR_FULL_LOAD = 18

    # Time to wait before next attempt to interact with web driver is made.
    # Used for page visit
    RETRY_TIME = 60

    # Threshold for using buffer instead of printing everything to the file
    # line by line
    BUFF_THRESHOLD = 30

    # List of file extensions to ignore if a resource with that
    # extension is visited
    INVALID_EXTENSIONS = [
        'mp4', 'jpg', 'png', 'jpeg',
        'zip', 'rar', 'xls', 'rtf',
        'docx', 'doc', 'pptx', 'ppt',
        'pdf', 'txt']

    # List of words that are relevant for the profile.
    # Program will match them with the URL and possibly prioritize
    # if requested
    RELEVANT_WORDS = [
        # en
        'profile', 'user', 'users',
        'about-us', 'team',
        'employees', 'staff', 'professor',

        # rs
        'profil',
        'o-nama',
        'zaposlen', 'nastavnik', 'nastavnici', 'saradnici', 'profesor', 'osoblje',
        'запослен', 'наставник', 'наставници', 'сарадници', 'професор', 'особље']

    # Suffix that is added to filename if file with default filename is present
    PRINT_SUFFIX_MIN = 100_000
    PRINT_SUFFIX_MAX = 999_999

    # Threshold value for detecting positive class
    PREDICTION_THRESHOLD = 0.5

    # The threshold determines the number of subpages of a URL that are categorized as profile pages.
    # Once this threshold is met, the URL is regarded as the parent page for all subsequent profile pages
    ORIGIN_PAGE_THRESHOLD = 3

    DEMO_MODEL_URL = 'https://huggingface.co/tsrdjan/scooby/resolve/main/scooby.h5'

    IMAGE_CLASSIFIERS = [
        'scooby']

    # Max lenght of the filename. This is desired limit. If target filesystem does not support
    # this lenght then it's limit will be used as maximum lenght
    # Note: Kaggle has limit of 99 characters for filename
    FILENAME_MAX_LENGHT = 99

    # Suffix that will be appended after cut if filename is too long.
    # Used to indicate that at that point where cropping happened.
    # There is also another part of the suffix which is appended to avoid same filename conflicts
    FILENAME_CUT_SUFFIX = '--CROP_'

    # Mapping for unsafe chars that may appear in the filename
    CHAR_REPLACEMENTS = {
                        '#': 'ANCH',
                        '?': 'QMARK',
                        '&': 'AMP',
                        '@': 'ATSGN',
                        '!': 'EMARK',
                        ':': 'COL',
                        ';': 'SEMICOL',
                        ',': 'COMMA',
                        "'": 'APOST',
                        '"': 'QUOTE',
                        '`': 'BTICK',
                        '(': 'BR',
                        ')': 'BR',
                        '{': 'CRBR',
                        '}': 'CRBR',
                        '[': 'SQBR',
                        ']': 'SQBR',
                        '<': 'LTHEN',
                        '>': 'GTHEN',
                        '/': '__',
                        '|': 'PIPE',
                        '\\': 'BSLASH',
                        '%': 'PERC',
                        '+': 'PLUS',
                        '*': 'STAR',
                        '=': 'EQL',
                        '^': 'CARET',
                        '~': 'TILDA'}
