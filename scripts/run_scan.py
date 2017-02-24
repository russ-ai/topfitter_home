#! /usr/bin/env python
"""\
%prog [opts]

Start running MadEvent samples in series (see make_batch_grid.py for parallel options) 
"""

import os, shutil, re, fileinput, glob
from subprocess import call
from sys import exit, stderr

import optparse
op = optparse.OptionParser(usage=__doc__)

op.add_option("--xsec",dest="XSEC", default=False, action="store_true", help="Get total cross-section only, no event plotting.")
op.add_option("--npts",dest="NSCAN", default=1000, type=int,help="number of scan points")
op.add_option("--nevts",dest="NEVTS", default=100000, type=int,help="number of events per run")
op.add_option("--info",dest="INFO", default=False, action="store_true", help="Print additional parameterinfo.")

opts, args = op.parse_args()

main=os.getcwd()

## make results directories
dirs=["results","samples/outputs","samples/Events"]
for d in dirs:
    shutil.rmtree(d,ignore_errors=True)
    os.mkdir(d)
outdir=os.path.join(main,"results")
    
## get number of parameter space points
size=opts.NSCAN 
dsize = len(os.walk("param_space").next()[1])
if size > dsize:
    print "Number of requested points exceeds number of available param space points. Exiting"
    exit(1)

## operators in model parameter card to scan
## ops=["CG","ReCuG33","C1qq1331","C8qu3311","C3qq1331","C8ud3311"]
ops=["ReCuB33","ReCuW33","ReCPhiu33","ReC1Phiq33","ReC3Phiq33"]

## start running MadEvent samples
for i in xrange(size):
    dname = "results/%03d" % i
    os.mkdir(dname)
    f = os.path.join('samples','Cards','param_card.dat')
    shutil.copy('param_card_sm.dat', f)
    shutil.copy(os.path.join('param_space','%03d' % i, 'used_params'),dname)
    
    ## match operators to parameter space point
    cs = []
    for ind, line in enumerate(open('param_space/%03d/used_params' % i )):
        cs.append(line.split()[1])
        cs[ind] = float(cs[ind])
    try:
        assert len(cs)==len(ops)        
    except:
        stderr.write("Number of operators must match dimensionality of parameter space. Exiting\n")
        exit(1)


    for line in fileinput.FileInput(f,inplace=1):
        for j in xrange(len(ops)):
            line = line.replace("0e-08 # %s " %ops[j], "%fe-08 # %s " % (cs[j], ops[j]))
        print line,
    for line in fileinput.FileInput(os.path.join('samples','Cards','run_card.dat'),inplace=1):
        line = line.replace("100000 = nevents", "%d = nevents" %opts.NEVTS )
        print line,

    if i == 1:
        import datetime
        start=datetime.datetime.now()
        

    ## generate events
    os.chdir('samples')
    g=open('outputs/' + 'output%03d' %i , 'w' )
    print 'At run %03d' % i
    if opts.INFO:
        print "Wilson coefficients:"
        for j in xrange(len(ops)):
            print "%s = %f [TeV^-2]" % (ops[j], cs[j]/100)
        print
    print 'Generating events'
    call(["./bin/generate_events","-f"], stdout=g )
    print 'Done'
    
    ## optionally plot events with FastPartons
    if not opts.XSEC:
        evtfile=os.path.join('Events','run_01','unweighted_events.lhe.gz')
        if os.path.exists(evtfile):
            shutil.move(evtfile,'Analysis')
            os.chdir('Analysis')

            ## compile analysis on first run
            if i==0:
                print "Building FastPartons"
                try:
                    assert(call(["make"],stdout=open(os.devnull, 'wb')) == 0)
                    print "Done"
                except:
                    stderr.write("Failed to build FastPartons. Exiting\n")
                    exit(1)

            ## plot events and delete after plotting
            call(["gunzip","unweighted_events.lhe.gz"])
            call(["./analysis", "unweighted_events.lhe" ])
            os.remove("unweighted_events.lhe")
            infiles = glob.glob("*.dat")

            ## check binning is same as kfactors
            if i==0:
                import numpy as np
                
                for infile in infiles:
                    npinfile = np.loadtxt(infile)
                    try:
                        kfile = np.loadtxt(os.path.join(main,"kfactors",infile))
                        assert len(npinfile) == len(kfile)
                    except AssertionError:
                        ans=raw_input("Warning: k-factor binning mismatch for %s. Continue anyway? (y/n) " % infile)
                    except IOError:
                        ans=raw_input("Warning: no k-factors for %s. Continue anyway? (y/n) " % infile)
                    if ans.lower()== ('y'):
                        continue
                    else: exit(1)
            [shutil.copy(i,os.path.join(main,dname)) for i in infiles]
        else:
            print 'Events were not generated for run %03d' % i
    else:
        f = 'outputs/' + 'output%03d' %i
        for line in open(f,"r"):
            if re.match("(.*)Cross-section(.*)", line):
                xsec = float(line.split()[2])
                xsec_err = float(line.split()[4])
                with open(os.path.join(main,dname,'xsec.dat'), 'w') as fout:
                    fout.write('%g  %g\n' % (xsec, xsec_err))
                    fout.close()

    if i==1:
        elapsed=datetime.datetime.now()
        totdur = (opts.NSCAN-1)*((elapsed-start))
        print "%d runs requested. Estimated finish time:" % opts.NSCAN
        print (start+totdur).ctime()
        print

    os.chdir(main)
    shutil.rmtree('samples/Events/run_01')
