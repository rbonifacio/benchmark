#!/bin/bash
source config.sh

# first parameter gives input dir and the second explicit/implicit
(test $# -lt 1) && (echo "too few arguments") && exit 0

srcdir=$TOOLHOME/$1
destdir=$TOOLHOME/cg.instrumented/$1
mkdir -p $destdir
timeout() {

    time=$1

    # start the command in a subshell to avoid problem with pipes
    # (spawn accepts one command)
    command="/bin/sh -c \"$2\""

    expect -c "set echo \"-noecho\"; set timeout $time; spawn -noecho $command; expect timeout { exit 1 } eof { exit 0 }"    

    if [ $? = 1 ] ; then
        echo "Timeout after ${time} seconds"
    fi

}

instr()
{
	for file in `ls $srcdir`
	do
        if [ -f "$destdir/$file" ]; then
            echo "Using instrumented $file ......"
        else
            echo "Instrumenting $file ......"
            timeout 1200 "$TOOLHOME/instrumentApp.sh $srcdir/$file $destdir"
            #echo "chapple" | $TOOLHOME/signandalign.sh $destdir/${i}/s.apk
        fi
       
	done
}

instr

exit 0
