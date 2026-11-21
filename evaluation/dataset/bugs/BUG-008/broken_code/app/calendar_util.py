def is_leap_year(year):
    if year % 100 == 0:
        return True
    return year % 4 == 0
