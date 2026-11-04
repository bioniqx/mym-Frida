%global frida_deps 20261022
%ifarch x86_64
%global frida_host linux-x86_64
%endif
%ifarch aarch64
%global frida_host linux-arm64
%endif

Name:           efni
Version:        1.0.0
Release:        1%{?dist}
Summary:        Building blocks for protocol-heavy GLib code
License:        wxWindows
URL:            https://github.com/frida/efni
Source0:        %{name}-%{version}.tar.xz
%ifarch x86_64
Source1:        https://build.frida.re/deps/%{frida_deps}/toolchain-linux-x86_64.tar.xz
%endif
%ifarch aarch64
Source1:        https://build.frida.re/deps/%{frida_deps}/toolchain-linux-arm64.tar.xz
%endif

BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  git
BuildRequires:  python3
BuildRequires:  glib2-devel
BuildRequires:  libgee-devel
BuildRequires:  json-glib-devel
BuildRequires:  gobject-introspection-devel

%description
Building blocks for protocol-heavy GLib code.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
Headers, Vala bindings and GObject introspection data for %{name}.

%prep
%autosetup
mkdir -p deps
cp %{SOURCE1} deps/
python3 releng/deps.py sync toolchain %{frida_host} deps/toolchain-%{frida_host}

%build
export FRIDA_VERSION=%{version}
./configure --prefix=%{_prefix} --enable-shared --enable-symbols --without-prebuilds=sdk
make

%install
DESTDIR=%{buildroot} make install

%files
%license COPYING
%{_libdir}/libefni-1.0.so.0*
%{_libdir}/girepository-1.0/Efni-1.0.typelib

%files devel
%{_includedir}/efni-1.0/
%{_libdir}/libefni-1.0.so
%{_libdir}/pkgconfig/efni-1.0.pc
%{_datadir}/gir-1.0/Efni-1.0.gir
%{_datadir}/vala/vapi/efni-1.0.vapi
%{_datadir}/vala/vapi/efni-1.0.deps

%changelog
* Tue Oct 20 2026 Ole André Vadla Ravnås <oleavr@frida.re> - 1.0.0-1
- Initial package
