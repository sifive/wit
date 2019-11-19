#!/bin/sh

. $(dirname $0)/test_util.sh

check "a is not b" [ "a" = "b" ]
finish
