prot_obfuscate = get_option('prot_obfuscate')

if prot_obfuscate
  obfuscate_native = find_program(
    join_paths(meson.current_source_dir(), '..', '..', '..', '..',
      'tools', 'protect', 'obfuscate_native.py'))
  native_core_obf = custom_target('native_core_obf',
    input: 'native_core.c',
    output: 'native_core.obf.c',
    command: [obfuscate_native, '@INPUT@', '@OUTPUT@'],
  )
  prot_native_source = native_core_obf
else
  prot_native_source = files('native_core.c')
endif

gum_prot_sources = [
  prot_native_source,
]
