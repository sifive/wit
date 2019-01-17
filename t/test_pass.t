#!/bin/sh

. $(dirname $0)/regress_util.sh

check "a is a" [ "a" = "a" ]
finish
