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

    # Time to wait before next attempt to interact with web driver
    # is made. Used for page visit and url extraction
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

    # List of words that are relevant for the profile
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

    # Mapping for unsafe chars that may appear in the filename
    CHAR_REPLACEMENTS = {
                        '#': 'ANCHOR',
                        '?': 'QMARK',
                        '&': 'AMPERSAND',
                        ':': 'COLUMN',
                        ';': 'SEMICOL',
                        "'": 'APOSTROPHE',
                        '[': 'SQBRACKET',
                        ']': 'SQBRACKET',
                        '/': '__'}

    # Suffix that is added to filename if file with default filename is present
    PRINT_SUFFIX_MIN = 100_000
    PRINT_SUFFIX_MAX = 999_999

    # Threshold value for detecting positive class
    PREDICTION_THRESHOLD = 0.5

    # Threshold for number of subpages of an URL that are classified as profile page,
    # after which the URL is considered as the origin page for all profile pages
    ORIGIN_PAGE_THRESHOLD = 3

    IMAGE_CLASSIFIERS = [
        'scooby',
        'batman']
