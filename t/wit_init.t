#!/bin/sh

wit init 
test $? -eq 2

wit init myws
test $? -eq 0
