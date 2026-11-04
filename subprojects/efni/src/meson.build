efni_sources = [
  'error.vala',
  'promise.vala',
  'buffer.vala',
  'buffer-glue.c',
  'value.vala',
  'stream.vala',
  'socket.vala',
  'socket-glue.c',
  'fs.vala',
  'marshal.vala',
  'numeric.vala',
  'debugger.vala',
  'gdb.vala',
]

efni_vala_args = [
  '--pkg=gio-2.0',
  '--pkg=json-glib-1.0',
]
if host_os_family != 'windows'
  efni_vala_args += '--pkg=gio-unix-2.0'
endif

efni_vapi_deps = ['gio-2.0', 'gee-0.8', 'json-glib-1.0']

if host_os_family == 'darwin'
  efni_sources += [
    'xpc.vala',
    'efni-darwin.c',
  ]
  darwin_vapi_deps = ['efni-darwin-gcd', 'efni-darwin-xpc']
  foreach dep : darwin_vapi_deps
    efni_vala_args += '--pkg=' + dep
  endforeach
  efni_vapi_deps += darwin_vapi_deps
  install_headers('efni-darwin.h', install_dir: header_install_dir)
  install_data(
    local_vapidir / 'efni-darwin-gcd.vapi',
    local_vapidir / 'efni-darwin-xpc.vapi',
    install_dir: vapidir,
  )
endif

deps_conf = configuration_data()
deps_conf.set('DEPS', '\n'.join(efni_vapi_deps))
configure_file(
  input: 'efni.deps.in',
  output: f'efni-@api_version@.deps',
  configuration: deps_conf,
  install_dir: vapidir,
)

vala_packages = []
foreach pkg : efni_vapi_deps
  if pkg != 'gee-0.8' or gee_dep.type_name() != 'internal'
    vala_packages += pkg
  endif
endforeach

efni_gir_name = f'Efni-@api_version@.gir'

efni = library('efni-' + api_version, efni_sources,
  c_args: component_cflags,
  vala_header: 'efni.h',
  vala_vapi: f'efni-@api_version@.vapi',
  vala_gir: efni_gir_name,
  vala_args: efni_vala_args,
  dependencies: [glib_dep, gobject_dep, gio_dep, gee_dep, json_glib_dep] + platform_deps,
  soversion: '0',
  install: true,
  install_dir: [true, header_install_dir, vapidir, girdir],
)

if build_typelib
  custom_target('efni-typelib',
    command: [
      gir_compiler,
      '--output', '@OUTPUT@',
      '--includedir=' + gi_girdir,
      meson.current_build_dir() / efni_gir_name,
    ],
    output: f'Efni-@api_version@.typelib',
    depends: efni,
    install: true,
    install_dir: typelibdir,
  )
endif

efni_dep = declare_dependency(
  include_directories: include_directories('.'),
  link_with: efni,
  dependencies: [glib_dep, gobject_dep, gio_dep, gee_dep, json_glib_dep] + platform_deps,
  variables: {
    'vapidir': local_vapidir,
    'girdir': meson.current_build_dir(),
    'vala_packages': ' '.join(vala_packages),
  },
)

meson.override_dependency(f'efni-@api_version@', efni_dep)

pkg = import('pkgconfig')
pkg.generate(efni,
  filebase: f'efni-@api_version@',
  name: 'Efni',
  version: meson.project_version(),
  description: 'Building blocks for protocol-heavy GLib code',
  requires: ['glib-2.0', 'gobject-2.0', 'gio-2.0', 'gee-0.8', 'json-glib-1.0'],
  variables: {'girdir': girdir, 'vapidir': vapidir},
  subdirs: f'efni-@api_version@',
)
