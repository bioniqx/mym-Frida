namespace Efni {
	public errordomain Error {
		/**
		 * The backing service is not running.
		 */
		SERVER_NOT_RUNNING,
		/**
		 * An argument was invalid.
		 */
		INVALID_ARGUMENT,
		/**
		 * The operation is not valid in the current state.
		 */
		INVALID_OPERATION,
		/**
		 * Permission was denied.
		 */
		PERMISSION_DENIED,
		/**
		 * The requested address is already in use.
		 */
		ADDRESS_IN_USE,
		/**
		 * The operation timed out.
		 */
		TIMED_OUT,
		/**
		 * The operation is not supported.
		 */
		NOT_SUPPORTED,
		/**
		 * A protocol error occurred.
		 */
		PROTOCOL,
		/**
		 * A transport-level error occurred.
		 */
		TRANSPORT
	}

	/**
	 * Rethrows an error caught as {@link GLib.Error} where only
	 * {@link Error} and {@link GLib.IOError.CANCELLED} may occur.
	 */
	[NoReturn]
	public void throw_api_error (GLib.Error e) throws Error, IOError {
		if (e is Error)
			throw (Error) e;

		if (e is IOError.CANCELLED)
			throw (IOError) e;

		assert_not_reached ();
	}
}
