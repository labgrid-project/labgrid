
var_dict = {}

def add_var(name, value):
  var_dict[name] = value

def get_var(name, default=None):
  return var_dict.get(name, default)
