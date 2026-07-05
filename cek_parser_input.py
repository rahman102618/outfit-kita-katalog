import importlib.util
spec = importlib.util.spec_from_file_location('mp', 'manage_products.py')
mp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mp)

print('Tempel 1 baris input produk, lalu ENTER:')
line = input('> ')
print('\nHASIL PARSER:')
print(mp.parse_input_line_data(line))
print('\nENTRY:')
print(mp.parse_numbered_link_entries(line, []))
