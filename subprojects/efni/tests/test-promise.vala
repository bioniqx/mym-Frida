namespace Efni.PromiseTest {
	public void add_tests () {
		GLib.Test.add_func ("/Promise/resolves-before-await", () => {
			var h = new Harness ((h) => resolves_before_await.begin (h as Harness));
			h.run ();
		});

		GLib.Test.add_func ("/Promise/resolves-after-await", () => {
			var h = new Harness ((h) => resolves_after_await.begin (h as Harness));
			h.run ();
		});

		GLib.Test.add_func ("/Promise/rejection-surfaces-as-efni-error", () => {
			var h = new Harness ((h) => rejection_surfaces_as_efni_error.begin (h as Harness));
			h.run ();
		});

		GLib.Test.add_func ("/Promise/foreign-rejection-is-wrapped", () => {
			var h = new Harness ((h) => foreign_rejection_is_wrapped.begin (h as Harness));
			h.run ();
		});

		GLib.Test.add_func ("/Promise/await-honors-cancellation", () => {
			var h = new Harness ((h) => await_honors_cancellation.begin (h as Harness));
			h.run ();
		});

		GLib.Test.add_func ("/Promise/then-runs-once-ready", () => {
			var h = new Harness ((h) => then_runs_once_ready.begin (h as Harness));
			h.run ();
		});
	}

	private async void resolves_before_await (Harness h) {
		var promise = new Promise<int> ();
		promise.resolve (42);

		try {
			int result = yield promise.future.wait_async (null);
			assert_true (result == 42);
			assert_true (promise.future.ready);
		} catch (GLib.Error e) {
			assert_not_reached ();
		}

		h.done ();
	}

	private async void resolves_after_await (Harness h) {
		var promise = new Promise<string> ();
		Timeout.add (10, () => {
			promise.resolve ("done");
			return false;
		});

		try {
			string result = yield promise.future.wait_async (null);
			assert_cmpstr (result, EQ, "done");
		} catch (GLib.Error e) {
			assert_not_reached ();
		}

		h.done ();
	}

	private async void rejection_surfaces_as_efni_error (Harness h) {
		var promise = new Promise<bool> ();
		promise.reject (new Error.TIMED_OUT ("too slow"));

		try {
			yield promise.future.wait_async (null);
			assert_not_reached ();
		} catch (Error e) {
			assert_true (e is Error.TIMED_OUT);
			assert_cmpstr (e.message, EQ, "too slow");
		} catch (IOError e) {
			assert_not_reached ();
		}

		h.done ();
	}

	private async void foreign_rejection_is_wrapped (Harness h) {
		var promise = new Promise<bool> ();
		promise.reject (new IOError.CONNECTION_CLOSED ("peer went away"));

		try {
			yield promise.future.wait_async (null);
			assert_not_reached ();
		} catch (Error e) {
			assert_true (e is Error.TRANSPORT);
			assert_cmpstr (e.message, EQ, "peer went away");
		} catch (IOError e) {
			assert_not_reached ();
		}

		h.done ();
	}

	private async void await_honors_cancellation (Harness h) {
		var promise = new Promise<bool> ();
		var cancellable = new Cancellable ();
		Timeout.add (10, () => {
			cancellable.cancel ();
			return false;
		});

		try {
			yield promise.future.wait_async (cancellable);
			assert_not_reached ();
		} catch (Error e) {
			assert_not_reached ();
		} catch (IOError e) {
			assert_true (e is IOError.CANCELLED);
		}

		h.done ();
	}

	private async void then_runs_once_ready (Harness h) {
		var promise = new Promise<int> ();
		bool handled = false;
		int seen = 0;

		promise.future.then (f => {
			handled = true;
			seen = f.value;
			then_runs_once_ready.callback ();
		});

		assert_false (handled);
		promise.resolve (7);

		yield;

		assert_true (handled);
		assert_true (seen == 7);

		h.done ();
	}

	private class Harness : Test.AsyncHarness {
		public Harness (owned Test.AsyncHarness.TestSequenceFunc func) {
			base ((owned) func);
		}
	}
}
