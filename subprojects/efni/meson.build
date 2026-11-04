project('efni', 'vala', 'c',
  version: run_command(find_program('python3'), files('tools' / 'detect-version.py'),
    capture: true,
    check: true).stdout().strip(),
  meson_version: '>=1.1.0',
  default_options: ['c_std=gnu99,c99'],
)

fs = import('fs')
cc = meson.get_compiler('c')

api_version = '1.0'

host_os_family = host_machine.system()
if host_os_family == 'android'
  host_os_family = 'linux'
endif
host_os = host_machine.subsystem().split('-')[0]

glib_dep = dependency('glib-2.0')
gobject_dep = dependency('gobject-2.0')
gio_dep = dependency('gio-2.0')
gee_dep = dependency('gee-0.8', default_options: [
  'default_library=static',
  'disable-introspection=true',
])
json_glib_dep = dependency('json-glib-1.0', version: '>=1.8', default_options: [
  'default_library=static',
  'introspection=disabled',
  'gtk_doc=disabled',
  'tests=false',
  'nls=disabled',
])

platform_deps = []
if host_os_family != 'windows'
  platform_deps += dependency('gio-unix-2.0')
endif

local_vapidir = meson.current_source_dir() / 'vapi'

vala_flags = [
  '--vapidir=' + local_vapidir,
  '--define=' + host_os_family.to_upper(),
]
if host_os != host_os_family
  vala_flags += '--define=' + host_os.to_upper()
endif
if glib_dep.type_name() == 'pkgconfig'
  glib_version = glib_dep.version().split('.')
  vala_flags += '--target-glib=@0@.@1@'.format(glib_version[0], glib_version[1])
endif
if gee_dep.type_name() not in ['internal', 'cmake']
  gee_prefix = gee_dep.get_variable('prefix', default_value: '')
  if gee_prefix != ''
    gee_vapidir = gee_prefix / 'share' / 'vala' / 'vapi'
    if fs.is_dir(gee_vapidir)
      vala_flags += '--vapidir=' + gee_vapidir
    endif
  endif
endif
add_project_arguments(vala_flags, language: 'vala')

c_flags = ['-DHAVE_' + host_os_family.to_upper()]
if host_os != host_os_family
  c_flags += '-DHAVE_' + host_os.to_upper()
endif
add_project_arguments(c_flags, language: 'c')

component_cflags = []
ndebug = get_option('b_ndebug')
if ndebug == 'true' or (ndebug == 'if-release' and not get_option('debug'))
  component_cflags += [
    '-DG_DISABLE_ASSERT',
    '-DG_DISABLE_CHECKS',
    '-DG_DISABLE_CAST_CHECKS',
  ]
endif

gi_dep = dependency('gobject-introspection-1.0', required: false)
girdir = get_option('prefix') / get_option('datadir') / 'gir-1.0'
typelibdir = get_option('prefix') / get_option('libdir') / 'girepository-1.0'
gir_compiler = find_program('gi-compile-repository', 'g-ir-compiler', required: false)
build_typelib = gi_dep.found() and gir_compiler.found()
if build_typelib
  gi_girdir = gi_dep.get_variable('girdir')
  foreach gir : ['Gio-2.0.gir', 'Gee-0.8.gir', 'Json-1.0.gir']
    build_typelib = build_typelib and fs.exists(gi_girdir / gir)
  endforeach
endif
vapidir = get_option('prefix') / get_option('datadir') / 'vala' / 'vapi'
header_install_dir = get_option('includedir') / f'efni-@api_version@'

tests_opt = get_option('tests')
if tests_opt.auto()
  build_tests = not meson.is_subproject() and meson.can_run_host_binaries()
else
  build_tests = not tests_opt.disabled()
endif

subdir('src')
if build_tests
  subdir('tests')
endif
