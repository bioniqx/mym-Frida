namespace Efni.Numeric {
	public uint int64_hash (int64? val) {
		uint64 v = (uint64) val.abs ();
		return (uint) ((v >> 32) ^ (v & 0xffffffffU));
	}

	public bool int64_equal (int64? val_a, int64? val_b) {
		int64 a = val_a;
		int64 b = val_b;
		return a == b;
	}

	public uint uint64_hash (uint64? val) {
		uint64 v = val;
		return (uint) ((v >> 32) ^ (v & 0xffffffffU));
	}

	public bool uint64_equal (uint64? val_a, uint64? val_b) {
		uint64 a = val_a;
		uint64 b = val_b;
		return a == b;
	}

	public uint bytes_hash (Bytes b) {
		return b.hash ();
	}

	public bool bytes_equal (Bytes a, Bytes b) {
		return a.compare (b) == 0;
	}
}
