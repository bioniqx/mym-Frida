namespace Efni.Marshal {
	public T enum_from_nick<T> (string nick) throws Error {
#if GLIB_2_84
		unowned EnumClass klass = (EnumClass) typeof (T).class_get ();
#else
		EnumClass klass = (EnumClass) typeof (T).class_ref ();
#endif
		var v = klass.get_value_by_nick (nick);
		if (v == null)
			throw new Error.INVALID_ARGUMENT ("Invalid %s", klass.get_type ().name ());
		return (T) v.value;
	}

	public string enum_to_nick<T> (int val) {
#if GLIB_2_84
		unowned EnumClass klass = (EnumClass) typeof (T).class_get ();
#else
		EnumClass klass = (EnumClass) typeof (T).class_ref ();
#endif
		unowned EnumValue? v = klass.get_value (val);
		if (v == null)
			return "unknown-0x%x".printf (val);
		return v.value_nick;
	}
}
