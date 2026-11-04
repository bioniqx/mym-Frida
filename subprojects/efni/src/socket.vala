namespace Efni {
	public SocketConnectable parse_socket_address (string? address, uint16 port, string default_address,
			uint16 default_port) throws Error {
		if (address == null)
			address = default_address;
		if (port == 0)
			port = default_port;

#if !WINDOWS
		if (address.has_prefix ("unix:")) {
			string path = address.substring (5);

			UnixSocketAddressType type = UnixSocketAddress.abstract_names_supported ()
				? UnixSocketAddressType.ABSTRACT
				: UnixSocketAddressType.PATH;

			return new UnixSocketAddress.with_type (path.to_utf8 (), type);
		}
#endif

		try {
			return NetworkAddress.parse (address, port);
		} catch (GLib.Error e) {
			throw new Error.INVALID_ARGUMENT ("%s", e.message);
		}
	}

	namespace UnixSocket {
		public extern void tune_buffer_sizes (int fd);
	}

	namespace Tcp {
		public extern void enable_nodelay (Socket socket);
	}

	namespace Udp {
		public size_t recv (uint8[] data, DatagramBased source, Cancellable? cancellable, out InetSocketAddress remote_address)
				throws Error, IOError {
			var v = InputVector ();
			v.buffer = data;
			v.size = data.length;

			InputVector[] vectors = { v };

			var m = InputMessage ();
			remote_address = null;
			m.address = &remote_address;
			m.vectors = vectors;
			m.num_vectors = vectors.length;

			InputMessage[] messages = { m };

			try {
				source.receive_messages (messages, 0, 0, cancellable);
			} catch (GLib.Error e) {
				throw new Error.TRANSPORT ("%s", e.message);
			}

			return messages[0].bytes_received;
		}

		public void send (uint8[] data, DatagramBased sink, Cancellable? cancellable) throws Error, IOError {
			send_to (data, null, sink, cancellable);
		}

		public void send_to (uint8[] data, InetSocketAddress? dest_addr, DatagramBased sink, Cancellable? cancellable)
				throws Error, IOError {
			var v = OutputVector ();
			v.buffer = data;
			v.size = data.length;

			OutputVector[] vectors = { v };

			var m = OutputMessage ();
			m.address = dest_addr;
			m.vectors = vectors;
			m.num_vectors = vectors.length;

			OutputMessage[] messages = { m };

			try {
				sink.send_messages (messages, 0, 0, cancellable);
			} catch (GLib.Error e) {
				throw new Error.TRANSPORT ("%s", e.message);
			}
		}
	}

}
