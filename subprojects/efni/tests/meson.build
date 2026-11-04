test_sources = [
  'main.vala',
  'runner.vala',
  'async-harness.vala',
  'test-buffer.vala',
  'test-promise.vala',
  'test-value.vala',
  'test-gdb.vala',
]

runner = executable('efni-tests', test_sources,
  vala_args: efni_vala_args,
  dependencies: [glib_dep, gobject_dep, gio_dep, gee_dep, json_glib_dep, efni_dep] + platform_deps,
)

test('efni', runner,
  timeout: 120,
)
