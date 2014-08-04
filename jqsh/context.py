class FilterContext:
    def __copy__(self):
        ret = FilterContext()
        ret.is_main = self.is_main
        return ret
    
    def __init__(self):
        """Creates the default context."""
        self.is_main = True
    
    def imported(self):
        """Returns a copy of self with is_main set to False."""
        ret = copy.copy(self)
        ret.is_main = False
        return ret
