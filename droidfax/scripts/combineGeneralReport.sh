#!/bin/bash
source config.sh

(test $# -lt 1) && (echo "too few arguments") && exit 0

outdir=$1
mkdir -p $outdir
for file in calleerank callerrank calleerankIns callerrankIns compdist edgefreq gdistcov gdistcovIns 
do
	cat generalReport/${file}.txt > $outdir/generalReport/${file}.txt
done
exit 0
