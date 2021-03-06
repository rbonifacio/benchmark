#!/bin/bash
source config.sh

(test $# -lt 1) && (echo "too few arguments") && exit 0

outdir=$1
mkdir -p $outdir
for file in gicc dataicc extraicc icclink bothdataicc icccov
do
	cat ICCReport/${file}.txt > $outdir/ICCReport/${file}.txt
done
exit 0
