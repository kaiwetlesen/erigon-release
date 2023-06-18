# Disable the debug package as we don't provide it:
%global debug_package %{nil}
# TODO: rig up debug package support with golang.

# The following conditional determine which version of Erigon we're building. They
# may be overrode by invoking rpmbuild with -D 'macroname "macro value here"'.

# Erigon version:
%define spec_pkg_ver %{?pkg_ver}%{!?pkg_ver:2.33.0}
# Supplementary files version:
%define spec_suppl_ver %{?suppl_ver}%{!?suppl_ver:0.2.0}
# GoLang version:
%define spec_go_ver %{?go_ver}%{!?go_ver:1.19.5}

Name:           erigon
Vendor:         Ledgerwatch
Version:        %{spec_pkg_ver}
Release:        0%{?dist}
Summary:        A very efficient next-generation Ethereum execution client
License:        LGPLv3
URL:            https://github.com/ledgerwatch/erigon

# File sources:
Source0:        https://github.com/%{vendor}/%{name}/archive/refs/tags/v%{version}.tar.gz
Source1:        https://github.com/kaiwetlesen/%{name}-release/archive/refs/tags/v%{spec_suppl_ver}.tar.gz

BuildRequires: libmdbx-devel, binutils, git, curl
%if "%{dist}" == ".el8"
BuildRequires: gcc-toolset-10-gcc
BuildRequires: gcc-toolset-10-gcc-c++
%else
BuildRequires: gcc >= 10
BuildRequires: gcc-c++ >= 10
%endif

%description
An implementation of Ethereum (aka "Ethereum execution client"), on the
efficiency frontier, written in Go, compatible with the proof-of-stake merge.


%prep
# Build fails with GCC Go, so die unless we can set that alternative:
%autosetup -b 1 -n %{name}-release-%{spec_suppl_ver}
%autosetup -b 0 -n %{name}-%{version}
# Apply git attributes to release code:
git clone --bare --depth 1 -b v%{version} https://github.com/%{vendor}/%{name}.git .git
git init
git checkout -f -b %{name}-v%{version} tags/v%{version}

# Clone these two guys into the Erigon code:
#git clone https://github.com/ledgerwatch/erigon-snapshot.git turbo/snapshotsync/snapshothashes/erigon-snapshots
#git clone https://github.com/ngosang/trackerslist.git cmd/downloader/trackers/trackerslist
#sed -e 's/-buildvcs=false//g' Makefile > Makefile.new && mv -f Makefile.new Makefile


%build
# Enable GCC v10 on older RHELs:
if [ -f /opt/rh/gcc-toolset-10/enable ]; then
    . /opt/rh/gcc-toolset-10/enable
    echo "Enabled GCC toolchain v10 for RedHat systems"
fi
# Map the uname -m style of MArches to Go variants:
export mach=$(uname -m | tr '[A-Z]' '[a-z]')
echo "Detected machine architecture ${mach}"
if [ "${mach}" == 'x86_64' ]; then
    go_mach='amd64'
elif [ "${mach}" == 'i386' ] || [ "${mach}" == 'i686' ]; then
    go_mach='386'
elif [ "${mach}" == 'aarch64' ]; then
	go_mach='arm64'
else
	go_mach='unknown'
fi
if [ "$go_mach" == 'unknown' ]; then
	echo "No known Go-machine match for architecture ${mach}"
	exit -1
fi
# Download a temporary Go build chain, and set up a couple useful Go utilities:
echo "Installing Go v%{spec_go_ver}.${go_mach} into ${PWD}/go for the ${mach} platform"
curl -sL https://go.dev/dl/go%{spec_go_ver}.linux-${go_mach}.tar.gz | tar -C ${PWD} -xz
export GOPATH="${PWD}/go"
export PATH="${GOPATH}/bin:${PATH}"
go install github.com/cpuguy83/go-md2man@latest
# Switch to the build directory and derive some important values:
cd %{_builddir}/%{name}-%{version}
export GIT_COMMIT="$(git rev-parse HEAD)"
export GIT_BRANCH="%{name}-v%{version}"
export GIT_TAG="v%{version}"
# Begin building:
echo "------------ Building Erigon $GIT_TAG from branch $GIT_BRANCH (commit $GIT_COMMIT) ------------"
make %{name} rpcdaemon sentry txpool downloader hack state integration observer rpctest
echo '# "%{name}" 1 "%{summary}" %{vendor} "User Manuals"' > %{name}.1.md
cat %{name}.1.md README.md | go-md2man > %{name}.1
%{__gzip} %{name}.1
%{__rm} %{name}.1.md
# Rename binaries with common names to [name]-[binary] scheme:
cd build/bin
for binary in *; do
    %{__strip} --strip-debug --strip-unneeded ${binary}
    if echo ${binary} | grep -qv '^%{name}'; then
        %{__mv} ${binary} %{name}-${binary}
    fi
done
# Trash the temporary Go build chain:
chmod -R ug+w ${GOPATH}
rm -rf ${GOPATH}
cd -


%install
%define build_srcdir  %{_builddir}/%{name}-%{version}
%define suppl_srcdir   %{_builddir}/%{name}-release-%{spec_suppl_ver}
%{__install} -m 0755 -D -s   %{build_srcdir}/build/bin/*       -t %{buildroot}%{_bindir}
%{__install} -m 0644 -D      %{build_srcdir}/README.md         -t %{buildroot}%{_datadir}/doc/%{name}
%{__install} -m 0644 -D      %{build_srcdir}/TESTING.md        -t %{buildroot}%{_datadir}/doc/%{name}
%{__install} -m 0644 -D      %{build_srcdir}/COPYING*          -t %{buildroot}%{_datadir}/licenses/%{name}
%{__install} -m 0644 -D      %{build_srcdir}/AUTHORS           -t %{buildroot}%{_datadir}/licenses/%{name}
%{__install} -m 0644 -D      %{build_srcdir}/%{name}.1.gz      -t %{buildroot}%{_mandir}/man1
%{__install} -m 0644 -D      %{suppl_srcdir}/units/*.service    -t %{buildroot}%{_prefix}/lib/systemd/system
%{__install} -m 0644 -D      %{suppl_srcdir}/firewallsvcs/*.xml -t %{buildroot}%{_prefix}/lib/firewalld/services
%{__install} -m 0644 -D      %{suppl_srcdir}/sysconfig/%{name}  -T %{buildroot}%{_sysconfdir}/sysconfig/%{name}


%files
%license COPYING COPYING.LESSER AUTHORS
%doc README.md TESTING.md
%{_bindir}/*
%{_mandir}/man1/%{name}.1.gz
%{_prefix}/lib/systemd/system/*
%{_prefix}/lib/firewalld/services/*
%config(noreplace) %{_sysconfdir}/sysconfig/%{name}


%pre
if ! getent group %{name} &> /dev/null; then
    groupadd -r %{name}
fi
if ! getent passwd %{name} &> /dev/null; then
    useradd -r -g %{name} -m -d %{_sharedstatedir}/%{name} -k /dev/null %{name}
fi


%changelog
* Tue Jan 10 2023 Kai Wetlesen <kwetlesen@mac.com> - 2.33.1-0%{?dist}
- This release marks the first independent release of the Erigon RPM
- All new versions of the Erigon RPM will be released by me personally
- Bumped Erigon version to 2.33.1, incorporating a critical bug fix from the Erigon team

* Fri Nov 4 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2.27.0-0%{?dist}
- Today marks the dawn of a new era when Erigon development embraces SemVer!
- All new versions from this day forth will release under the Erigon package atom
- Truthfully, the dev team made this change earlier, but I was on holiday
- Bumping to Erigon 2.27.0

* Fri Nov 4 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.10.01-0%{?dist}
- Bumping to Erigon2 to version 2022.10.01
- Bumping GoLang version to v1.19.3
- Final release of the Erigon2 package as we transition to semver
- New Erigon packages will continue under the `erigon` namespace

* Tue Sep 20 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.09.03-0%{?dist}
- Building Erigon2 v2022.09.03

* Tue Sep 20 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.09.02-0%{?dist}
- Building Erigon2 v2022.09.02, soon to be followed by v2022.09.03
- Bumped GoLang version to v1.19.1

* Mon Sep 12 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.09.01-1%{?dist}
- Removed the deprecated `cons' binary
- Corrected bogus spec date

* Mon Sep 12 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.09.01-0%{?dist}
- Bumped Erigon2 version to v2022.09.01

* Thu Sep 1 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.08.03-0%{?dist}
- Bumped Erigon2 version to v2022.08.03
- Bumped Go toolchain version to v1.19

* Tue Aug 16 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.08.02-0%{?dist}
- Bumped Erigon2 version to v2022.08.02

* Tue Aug 9 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.08.01-0%{?dist}
- Bumped Erigon2 version to v2022.08.01

* Tue Aug 2 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.07.04-0%{?dist}
- Bumped Erigon2 version to v2022.07.04
- Bumped GoLang version to patch v1.18.5
- Updated firewall rules to better reflect true purpose
- Included additional useful utilities and daemons in bundle

* Fri Jul 29 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.07.03-0%{?dist}
- Bumped Erigon2 version to v2022.07.03

* Tue Jul 12 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.07.02-0%{?dist}
- Major revamp of build specification
- GoLang now must be pulled independently due to lack of available v1.19 in RL8
- Renamed all services from Erigon to Erigon2
- Bumped build version to v2022.07.02

* Tue May 3 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.04.03-0%{?dist}
- First Erigon2 RPM release

* Mon Mar 28 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.04.02-0%{?dist}
- Fix for erroneous assert in MDBX
- Change of skip analysis optimisation parameter
- (from 2022.04.01) Fix for the integration tool, include reset for the Finish stage
- (from 2022.04.01) Fix for the tx pool panic whilst working with multiple sentries
- (from 2022.04.01) Fix for "all defaults" case when calling eth_estimateGas RPC method
- (from 2022.04.01) Updated all pre-verified hashes for Mainnet, Ropsten, and Sepolia

* Mon Mar 28 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.03.02-0%{?dist}
- Bumped the release to pull in patches to LibMDBX

* Thu Mar 24 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.03.01-1%{?dist}
- Bumped the release to pull in a new version of LibMDBX

* Tue Mar 1 2022  Kai Wetlesen <kaiw@semiotic.ai> - 2022.03.01-0%{?dist}
- Corrected erroneous service names in spec
- Removed "v" from the version tag
- Setting numeric release version to accomodate release bug fixes and updates
- Cleaned up cruft from the spec file

* Mon Feb 28 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.02.04-beta%{?dist}
- Large jump in Erigon version
- Removing "dangerous" commands from pre section

* Tue Jan 25 2022 Kai Wetlesen <kaiw@semiotic.ai> - 2022.01.02-beta%{?dist}
- First Erigon RPM release
