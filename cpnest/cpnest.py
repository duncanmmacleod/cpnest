#! /usr/bin/env python
# coding: utf-8

import sys
import os
import optparse as op
import numpy as np
import multiprocessing as mp
from multiprocessing import Process, Lock, Queue
from Sampler import *
from ctypes import c_int, c_double
from NestedSampling import *
from parameter import Event
from parameter import *
#import matplotlib.cm as cm

def compute_rate(dl_list,T):
    Dmax = np.median([e.dmax for e in dl_list])
    (idx,) = np.where([e.dl for e in dl_list] < Dmax)
    Vmax = (4.*np.pi*Dmax**3)/3.0
    return len(idx)/(Vmax*T)

def FindHeightForLevel(inArr, adLevels):
    # flatten the array
    oldshape = shape(inArr)
    adInput= reshape(inArr,oldshape[0]*oldshape[1])
    # GET ARRAY SPECIFICS
    nLength = np.size(adInput)
      
    # CREATE REVERSED SORTED LIST
    adTemp = -1.0 * adInput
    adSorted = np.sort(adTemp)
    adSorted = -1.0 * adSorted

    # CREATE NORMALISED CUMULATIVE DISTRIBUTION
    adCum = np.zeros(nLength)
    adCum[0] = adSorted[0]
    for i in xrange(1,nLength):
        adCum[i] = np.logaddexp(adCum[i-1], adSorted[i])
    adCum = adCum - adCum[-1]

    # FIND VALUE CLOSEST TO LEVELS
    adHeights = []
    for item in adLevels:
        idx=(np.abs(adCum-np.log(item))).argmin()
        adHeights.append(adSorted[idx])

    adHeights = np.array(adHeights)
    return adHeights

if __name__ == '__main__':
    parser = op.OptionParser()
    parser.add_option("-N", type="int", dest="Nlive", help="Number of Live points",default=1000)
    parser.add_option("-o", "--output", type="string", dest="output", help="Output folder", default=None)
    parser.add_option("-i", "--input", type="string", dest="input", help="Input folder", default=None)
    parser.add_option("-s", type="int", dest="seed", help="seed for the chain", default=0)
    parser.add_option("--verbose", type="int", dest="verbose", help="display progress information", default=1)
    parser.add_option("--maxmcmc", type="int", dest="maxmcmc", help="maximum number of mcmc steps", default=5000)
    parser.add_option("--nthreads", type="int", dest="nthreads", help="number of sampling threads to spawn", default=None)
    parser.add_option( "--sample-prior", action="store_true", dest="prior", help="draw NLIVE samples from the prior", default=False)
    parser.add_option("-e", "--events", type="int", dest="events_number", help="number of events to analyse")
    parser.add_option("--event-number", type="int", dest="event_number", help="event number to analyse", default=None)
    parser.add_option("--max-hosts", type="int", dest="max_hosts", help="maximum number of hosts to analyse", default=None)
    parser.add_option("--max-distance", type="float", dest="max_distance", help="maximum distance to consider", default=None)
    
    (options, args) = parser.parse_args()

    verbose_ns = False
    verbose_sam = False
    
    if options.verbose == 1:
        verbose_ns = True
    elif options.verbose == 2:
        verbose_ns = True
        verbose_sam = True

    port = 5555
    authkey = "12345"
    ip = "0.0.0.0"
    
    Nevents = options.events_number
    np.random.seed(options.seed)
    all_files = os.listdir(options.input)
    events_list = [f for f in all_files if 'EVENT' in f or 'event' in f]
    snr_threshold = 8.0
    
    if options.event_number is None:
        
        events = []
        
        for ev in events_list:
            event_file = open(options.input+"/"+ev+"/ID.dat","r")
            event_id,dl,sigma,snr,domega,stuff1,stuff2,stuff3,stuff4,stuff5,stuff6,m1,m2 = event_file.readline().split(None)
            ID = np.int(event_id)
            dl = np.float64(dl)
            sigma = np.float64(sigma)*dl
            if sigma <0.01: sigma = 1.0
            snr = np.float64(snr)
            m1 = np.float64(m1)
            m2 = np.float64(m2)
            domega = np.float64(domega)
            event_file.close()
            try:
                distance,dummy,redshifts,masses = np.loadtxt(options.input+"/"+ev+"/ERRORBOX.dat",unpack=True)
                redshifts = np.atleast_1d(redshifts)
                masses = np.atleast_1d(masses)
                events.append(Event(ID,dl,sigma,snr,domega,m1,m2,redshifts))
                sys.stderr.write("Selecting event %s at a distance %s (error %s), snr %s, hosts %d\n"%(event_id,dl,sigma,snr,len(redshifts)))
            except:
                sys.stderr.write("Event %s at a distance %s (error %s), snr %s has no hosts, skipping\n"%(event_id,dl,snr,sigma))

        if options.max_distance is not None:
            distance_limited_events = [e for e in events if e.dl < options.max_distance]
        else:
            distance_limited_events = [e for e in events]

        if options.max_hosts is not None:
             analysis_events = [e for e in distance_limited_events if len(e.redshifts) < options.max_hosts]
        else:
            analysis_events = [e for e in distance_limited_events]

    else:
        event_file = open(options.input+"/"+events_list[options.event_number]+"/ID.dat","r")
        event_id,dl,sigma,snr,domega,stuff1,stuff2,stuff3,stuff4,stuff5,stuff6,m1,m2 = event_file.readline().split(None)
        ID = np.int(event_id)
        dl = np.float64(dl)
        sigma = np.float64(sigma)*dl
        if sigma <0.01: sigma = 1.0
        snr = np.float64(snr)
        m1 = np.float64(m1)
        m2 = np.float64(m2)
        domega = np.float64(domega)
        event_file.close()
        try:
            distance,dummy,redshifts,masses = np.loadtxt(options.input+"/"+events_list[options.event_number]+"/ERRORBOX.dat",unpack=True)
            redshifts = np.atleast_1d(redshifts)
            masses = np.atleast_1d(masses)
            analysis_events = [Event(ID,dl,sigma,snr,domega,m1,m2,redshifts)]
            sys.stderr.write("Selecting event %s at a distance %s (error %s), snr %s, hosts %d\n"%(event_id,dl,sigma,snr,len(redshifts)))
        except:
            sys.stderr.write("Event %s at a distance %s (error %s), snr %s has no hosts, skipping\n"%(event_id,dl,snr,sigma))
            exit()

    sys.stderr.write("Selected %d events\n"%len(analysis_events))

    T = 5.0
    rate = 1e9*compute_rate(analysis_events,T)
    sys.stderr.write("Inferred rate of %.2f Gpc^-3 yr^-1\n"%(rate))

#    bounds = [[0.7,0.75],[0.2,0.4],[1.0,1000]]
    bounds = [[0.4,1.0],[0.0,1.0]]
    names = ['h','om']

    for e in analysis_events:
        zmin = np.min(e.redshifts)
        zmax = np.max(e.redshifts)
        bounds.append([zmin-0.0015,zmax+0.0015])
        names.append('z%d'%e.ID)

    out_folder = options.output

    os.system('mkdir -p %s'%(out_folder))
    if options.prior: analysis_events = None
    NS = NestedSampler(analysis_events,names,bounds,Nlive=options.Nlive,maxmcmc=options.maxmcmc,output=out_folder,verbose=verbose_ns,seed=options.seed,prior=options.prior)
    Evolver = Sampler(analysis_events,options.maxmcmc,names,bounds, verbose = verbose_sam)

    NUMBER_OF_PRODUCER_PROCESSES = options.nthreads
    NUMBER_OF_CONSUMER_PROCESSES = 1

    process_pool = []
    ns_lock = Lock()
    sampler_lock = Lock()
    queue = Queue()
    
    for i in xrange(0,NUMBER_OF_PRODUCER_PROCESSES):
        p = Process(target=Evolver.produce_sample, args=(ns_lock, queue, NS.jobID, NS.logLmin, options.seed+i,ip, port, authkey ))
        process_pool.append(p)
    for i in xrange(0,NUMBER_OF_CONSUMER_PROCESSES):
        p = Process(target=NS.nested_sampling_loop, args=(sampler_lock, queue, port, authkey))
        process_pool.append(p)
    for each in process_pool:
        each.start()
