namespace Efni.BufferTest {
	public void add_tests () {
		GLib.Test.add_func ("/Buffer/round-trips-scalars-and-strings", round_trips_scalars_and_strings);
		GLib.Test.add_func ("/Buffer/honors-byte-order", honors_byte_order);
		GLib.Test.add_func ("/Buffer/resolves-labels-against-base-address", resolves_labels_against_base_address);
		GLib.Test.add_func ("/Buffer/rejects-truncated-reads", rejects_truncated_reads);
	}

	private void round_trips_scalars_and_strings () {
		var bytes = new BufferBuilder (LITTLE_ENDIAN, 8)
			.append_uint8 (0x7f)
			.append_uint16 (0xbeef)
			.append_uint32 ((uint32) 0xdeadbeef)
			.append_uint64 (0x0123456789abcdef)
			.append_string ("hello")
			.append_pointer (0x1000)
			.build ();

		try {
			var reader = new BufferReader (new Buffer (bytes, LITTLE_ENDIAN, 8));
			assert_true (reader.read_uint8 () == 0x7f);
			assert_true (reader.read_uint16 () == 0xbeef);
			assert_true (reader.read_uint32 () == (uint32) 0xdeadbeef);
			assert_true (reader.read_uint64 () == 0x0123456789abcdef);
			assert_cmpstr (reader.read_string (), EQ, "hello");
			assert_true (reader.read_pointer () == 0x1000);
			assert_true (reader.offset == bytes.get_size ());
		} catch (Error e) {
			printerr ("%s\n", e.message);
			assert_not_reached ();
		}
	}

	private void honors_byte_order () {
		var le = new BufferBuilder (LITTLE_ENDIAN).append_uint32 (0x01020304).build ();
		var be = new BufferBuilder (BIG_ENDIAN).append_uint32 (0x01020304).build ();

		assert_true (le.get (0) == 0x04);
		assert_true (be.get (0) == 0x01);

		try {
			assert_true (new BufferReader (new Buffer (le, LITTLE_ENDIAN)).read_uint32 () == 0x01020304);
			assert_true (new BufferReader (new Buffer (be, BIG_ENDIAN)).read_uint32 () == 0x01020304);
		} catch (Error e) {
			assert_not_reached ();
		}
	}

	private void resolves_labels_against_base_address () {
		try {
			var builder = new BufferBuilder (LITTLE_ENDIAN, 8);
			builder
				.append_pointer_to_label ("payload")
				.append_uint64 (0)
				.append_label ("payload")
				.append_string ("data");

			var bytes = builder.try_build (0x4000);

			var reader = new BufferReader (new Buffer (bytes, LITTLE_ENDIAN, 8));
			assert_true (reader.read_pointer () == 0x4000 + 16);
		} catch (Error e) {
			printerr ("%s\n", e.message);
			assert_not_reached ();
		}
	}

	private void rejects_truncated_reads () {
		var bytes = new BufferBuilder (LITTLE_ENDIAN).append_uint16 (42).build ();
		var reader = new BufferReader (new Buffer (bytes, LITTLE_ENDIAN));

		try {
			reader.read_uint32 ();
			assert_not_reached ();
		} catch (Error e) {
			assert_true (e is Error.PROTOCOL);
		}
	}
}
