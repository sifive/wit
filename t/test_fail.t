#!/bin/sh

. $(dirname $0)/regress_util.sh

check "a is not b" [ "a" = "b" ]
finish
