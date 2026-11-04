namespace Efni.ValueTest {
	public void add_tests () {
		GLib.Test.add_func ("/Value/VariantReader/reads-nested-members", variant_reader_reads_nested_members);
		GLib.Test.add_func ("/Value/VariantReader/rejects-missing-member", variant_reader_rejects_missing_member);
		GLib.Test.add_func ("/Value/JsonObjectReader/reads-members-and-elements", json_reader_reads_members_and_elements);
		GLib.Test.add_func ("/Value/JsonObjectReader/rejects-invalid-document", json_reader_rejects_invalid_document);
	}

	private void variant_reader_reads_nested_members () {
		var builder = new VariantBuilder (VariantType.VARDICT);
		builder.add ("{sv}", "name", new Variant.string ("efni"));
		builder.add ("{sv}", "version", new Variant.int64 (3));
		var tags = new VariantBuilder (new VariantType ("av"));
		tags.add ("v", new Variant.string ("a"));
		tags.add ("v", new Variant.string ("b"));
		builder.add ("{sv}", "tags", tags.end ());

		var reader = new VariantReader (builder.end ());
		try {
			assert_true (reader.has_member ("name"));
			assert_cmpstr (reader.read_member ("name").get_string_value (), EQ, "efni");
			reader.end_member ();

			assert_true (reader.read_member ("version").get_int64_value () == 3);
			reader.end_member ();

			reader.read_member ("tags");
			assert_true (reader.count_elements () == 2);
			assert_cmpstr (reader.read_element (1).get_string_value (), EQ, "b");
			reader.end_element ();
			reader.end_member ();
		} catch (Error e) {
			printerr ("%s\n", e.message);
			assert_not_reached ();
		}
	}

	private void variant_reader_rejects_missing_member () {
		var builder = new VariantBuilder (VariantType.VARDICT);
		builder.add ("{sv}", "present", new Variant.boolean (true));

		var reader = new VariantReader (builder.end ());
		try {
			reader.read_member ("absent");
			assert_not_reached ();
		} catch (Error e) {
			assert_true (e is Error.PROTOCOL);
		}
	}

	private void json_reader_reads_members_and_elements () {
		try {
			var reader = new JsonObjectReader ("""{"name": "efni", "count": 2, "items": ["x", "y"]}""");

			assert_true (reader.has_member ("name"));
			assert_false (reader.has_member ("missing"));

			assert_cmpstr (reader.read_member ("name").get_string_value (), EQ, "efni");
			reader.end_member ();

			assert_true (reader.read_member ("count").get_int64_value () == 2);
			reader.end_member ();

			reader.read_member ("items");
			assert_true (reader.count_elements () == 2);
			assert_cmpstr (reader.read_element (0).get_string_value (), EQ, "x");
			reader.end_element ();
			reader.end_member ();
		} catch (Error e) {
			printerr ("%s\n", e.message);
			assert_not_reached ();
		}
	}

	private void json_reader_rejects_invalid_document () {
		try {
			new JsonObjectReader ("{not json");
			assert_not_reached ();
		} catch (Error e) {
			assert_true (e is Error.INVALID_ARGUMENT);
		}
	}
}
