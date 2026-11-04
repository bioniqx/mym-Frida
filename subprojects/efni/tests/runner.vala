namespace Efni.Test {
	public void run (string[] args) {
		Environment.set_variable ("G_DEBUG", "fatal-warnings:fatal-criticals", true);
		GLib.Test.init (ref args);

		Efni.BufferTest.add_tests ();
		Efni.PromiseTest.add_tests ();
		Efni.ValueTest.add_tests ();
		Efni.GDBTest.add_tests ();

		GLib.Test.run ();
	}
}
