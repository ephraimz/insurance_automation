def change_url(original_url, new_str):
    """
    Finds /=// and creates a new URL with
    given string after /=//.
    """
    ind = '/=//'
    indloc = original_url.index(ind)
    return original_url[:indloc+len(ind)] + new_str
