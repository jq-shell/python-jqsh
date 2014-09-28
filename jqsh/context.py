class FilterContext:
    def __copy__(self):
        ret = FilterContext()
        ret.argv = self.argv[:]
        ret.is_main = self.is_main
        return ret
    
    def __init__(self):
        """Creates the default context."""
        import jqsh.functions
        
        self.argv = []
        self.get_builtin = jqsh.functions.get_builtin
        self.is_main = True
    
    @classmethod
    def command_line_context(cls, argv):
        ret = cls()
        ret.argv = list(argv)
        return ret
    
    def imported(self):
        """Returns a copy of self with is_main set to False."""
        ret = copy.copy(self)
        ret.is_main = False
        return ret
