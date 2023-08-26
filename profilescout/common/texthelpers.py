def longest_common_substring(str1, str2, case_sensitive=True):
    m = len(str1)
    n = len(str2)
    if not case_sensitive:
        str1 = str1.lower()
        str2 = str2.lower()
    # create a table to store the lengths of common substrings
    table = [[0] * (n + 1) for _ in range(m + 1)]
    # variables to keep track of the longest common substring
    max_length = 0
    end_index = 0
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if str1[i - 1] == str2[j - 1]:
                table[i][j] = table[i - 1][j - 1] + 1
                if table[i][j] > max_length:
                    max_length = table[i][j]
                    end_index = i
    # extract the longest common substring
    longest_substring = str1[end_index - max_length: end_index]
    return longest_substring
