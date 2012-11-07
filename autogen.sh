#!/bin/sh

test -n "${srcdir}" || srcdir=`dirname "$0"`
test -n "${srcdir}" || srcdir="$(pwd)"

olddir="$(pwd)"
cd "$srcdir"

#http://permalink.gmane.org/gmane.comp.education.sugar.devel/35523
mkdir m4

mkdir m4

intltoolize
autoreconf -i

cd "$olddir"
"$srcdir/configure" --enable-maintainer-mode "$@"
