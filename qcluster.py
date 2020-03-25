import pickle
import os,sys,psutil
import re
from time import strftime,sleep
import datetime
import kernelcompare 
import traceback
import shutil
from numpy import log
from random import randint,seed,shuffle
import logging
from helpers import Helper
import multiprocessing as mp
from multiprocessing.managers import BaseManager
from queue import Queue

class QueueManager(BaseManager): pass

class TheQManager(mp.Process):
    def __init__(self,,address):
        self.address=address
        super(TheQManager,self).__init__()
        
    def run(self):
        logdir=os.path.join(os.getcwd(),'log')
        if not os.path.exists(logdir): os.mkdir(logdir)
        handlername=os.path.join(logdir,f'TheQManager-log')
        logging.basicConfig(
            handlers=[logging.handlers.RotatingFileHandler(handlername, maxBytes=10**7, backupCount=1)],
            level=logging.DEBUG,
            format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
            datefmt='%Y-%m-%dT%H:%M:%S')
        self.logger = logging.getLogger(handlername)
        jobq = Queue()
        saveq = Queue()
        QueueManager.register('jobq', callable=lambda:jobq)
        QueueManager.register('saveq', callable=lambda:saveq)
        m = QueueManager(address=(self.address, 50000), authkey=b'qkey')
        s = m.get_server()
        self.logger.info('TheQManager starting')
        s.serve_forever()
        
class SaveQDumper(mp.Process):
    def __init__(self,address):
        self.address=address
        logdir=os.path.join(os.getcwd(),'log')
        if not os.path.exists(logdir): os.mkdir(logdir)
        handlername=os.path.join(logdir,f'SaveQDumper-log')
        logging.basicConfig(
            handlers=[logging.handlers.RotatingFileHandler(handlername, maxBytes=10**7, backupCount=1)],
            level=logging.DEBUG,
            format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
            datefmt='%Y-%m-%dT%H:%M:%S')
        self.logger = logging.getLogger(handlername)
        self.logger.info('SaveQDumper starting')
        
        super(SaveQDumper,self).__init__()
        
    def run(self):
        QueueManager.register('saveq')
        m = QueueManager(address=(self.address, 50000), authkey=b'saveq')
        m.connect()
        queue = m.saveq()
        keepgoing=1
        
        while keepgoing:
            success=0
            try:
                model_save=queue.get()
                success=1
            except:
                if queue.empty():
                    sleep(4)
                else:
                    self.logger.exception('')
            if success:
                if type(model_save) is str:
                    if model_save=='shutdown':
                        self.logger.warning(f'SaveQDumper shutting down')
                        return
                savepath=model_save['savepath']
                self.savepickle(model_save,savepath)
            
            
            
class JobQFiller(mp.Process):
    def __init__:(self,joblist,address):
        self.joblist=joblist
        self.address=address
        logdir=os.path.join(os.getcwd(),'log')
        if not os.path.exists(logdir): os.mkdir(logdir)
        handlername=os.path.join(logdir,f'JobQFiller-log')
        logging.basicConfig(
            handlers=[logging.handlers.RotatingFileHandler(handlername, maxBytes=10**7, backupCount=1)],
            level=logging.DEBUG,
            format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
            datefmt='%Y-%m-%dT%H:%M:%S')
        self.logger = logging.getLogger(handlername)
        self.logger.info('JobQFiller starting')
        super(JobQFiller,self).__init__()
        
    def run(self):
        QueueManager.register('jobq')
        m = QueueManager(address=(self.address, 50000), authkey=b'jobq')
        m.connect()
        queue = m.jobq()
        jobcount=len(self.joblist)
        i=1
        while self.joblist:
            job=self.joblist.pop()
            if not os.path.exists(job['savepath']):
                self.savepickle(job,job['jobpath'])#just for documentation
                try:
                    self.logger.debug(f'adding job:{i}/{jobcount} to job queue')
                    queue.put(job)
                    i+=1
                    self.logger.debug(f'job:{i}/{jobcount} succesfully added to queue')
                except:
                    self.joblist.append(job)
                    if queue.full()
                        sleep(4)
                    else:
                        self.logger.exception('jobq error for i:{i}')
            else:
                self.logger.info(f'JobQFiller is skipping job b/c saved at savepath:{job['savepath']}')
        self.logger.info('JobQFiller exiting')            
        return

                

class RunNode(mp.Process):
    def __init__(self,local_run=None):
        if local_run:
            self.address='127.0.0.1'
        else:
            self.address='192.168.1.89'
        address=self.address
        super(RunNode,self).__init__()
        
    def run(self,):
        platform=sys.platform
        p=psutil.Process(os.getpid())
        if platform=='win32':
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            p.nice(6)
        return self.initialize(myname)
        QueueManager.register('jobq')
        QueueManager.register('saveq')
        m = QueueManager(address=(self.address, 50000), authkey=b'qkey')
        m.connect()
        jobq = m.jobq()
        saveq = m.saveq()
        kc=kernelcompare.KernelCompare()
        while True:
            try:
                havejob=0
                jobsuccess=0
                saveqsuccess=0
                try:
                    rundict=jobq.get()
                    havejob=1
                except:
                    self.logger.exception('')
                if havejob:
                    if type(rundict) is str:
                        if rundict=='shutdown':
                            return
                    my_optimizedict=rundict['optimizedict']
                    my_datagen_dict=rundict['datagen_dict']
                    try:
                        jobsavepath=rundict['savepath']
                        jobsavefolder=os.path.split(jobsavepath)
                        if not os.path.exists(jobsavefolder):os.makedirs(jobsavefolder)
                        kc.run_model_as_node(my_optimizedict,my_datagen_dict,force_start_params=1)
                        jobsuccess=1
                    except:
                        self.logger.exception('putting job back in jobq')
                        jobq.put(rundict)
                        self.logger.debug('job back in jobq')
                    if jobsuccess:
                        model_save=self.getpickle(jobsavepath)
                        saveq.put(model_save)
                        
            except:
                self.logger.exception('')           
    
    
class RunCluster(kernelcompare.KernelCompare):
    '''
    '''
    
    def __init__(self,source=None,optdict_variation_list=None,datagen_variation_list=None,dosteps=1,local_run=None):
        if local_run:
            self.address='127.0.0.1'
        else:
            self.address='192.168.1.89'
            
        qm=TheQManager(self.address)
        qm.start()
        
        seed(1)        
        self.dosteps=dosteps
        self.optdict_variation_list=optdict_variation_list
        self.datagen_variation_list=datagen_variation_list
        if source is None: source='monte'
        self.source=source
        self.savedirectory='results'
        
        logdir=os.path.join(os.getcwd(),'log')
        if not os.path.exists(logdir): os.mkdir(logdir)
        handlername=os.path.join(logdir,f'mycluster_{myname}.log')
        logging.basicConfig(
            handlers=[logging.handlers.RotatingFileHandler(handlername, maxBytes=10**7, backupCount=1)],
            level=logging.DEBUG,
            format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
            datefmt='%Y-%m-%dT%H:%M:%S')
        self.logger = logging.getLogger(handlername)
        
       
        self.stepcount=5
        kernelcompare.KernelCompare.__init__(self,directory=self.savedirectory,source=source)
        self.jobdirectory=os.path.join(self.savedirectory,'jobs')
        self.modelsavedirectory=os.path.join(self.savedirectory,'saves')
        if not os.path.exists(self.jobdirectory): os.mkdir(self.jobdirectory)
        if not os.path.exists(self.modelsavedirectory): os.mkdir(self.modelsavedirectory)
            self.mastermaster() 
        

        #p#rint(f'datagen_variation_list:{datagen_variation_list}')
        self.initialize(myname)

    def generate_rundicts_from_variations(self,step=None):
        if self.optdict_variation_list is None:
            self.optdict_variation_list=self.getoptdictvariations(source=self.source)
        if self.datagen_variation_list is None:
            self.datagen_variation_list=self.getdatagenvariations(source=self.source)
        initial_datagen_dict=self.setdata(self.source)
        list_of_run_dicts=self.prep_model_list(optdict_variation_list=self.optdict_variation_list,datagen_variation_list=self.datagen_variation_list,datagen_dict=initial_datagen_dict)
        #list_of_run_dicts=list_of_run_dicts[-1::-1]#reverse the order of the list
        self.setup_save_paths(list_of_run_dicts,step=step)
        #p#rint(f'list_of_run_dicts[0:2]:{list_of_run_dicts[0:2]},{list_of_run_dicts[-2:]}')
        return list_of_run_dicts
    
    
    def setup_save_paths(self,rundictlist,step=None):
        if step is None:
            step=0
        for idx,rundict in enumerate(rundictlist):
            jobstepdir=os.path.join(self.jobdirectory,'step'+str(step))
            if not os.path.exists(jobstepdir): os.mkdir(jobstepdir)
            jobpath=os.path.join(jobstepdir,str(idx)+'_jobdict')
            try: species=rundict['datagen_dict']['species']
            except: 
                self.logger.exception('')
                species=''
            savestepdir=os.path.join(self.modelsavedirectory,'step'+str(step))
            if not os.path.exists(savestepdir): os.mkdir(savestepdir)
            savepath=os.path.join(savestepdir,'species-'+species+'_model_save_'+str(idx))
            rundict['jobpath']=jobpath
            rundict['savepath']=savepath

    def mastermaster(self,):
        
        
        if not self.dosteps:
            list_of_run_dicts=self.generate_rundicts_from_variations()
            return self.runmaster(list_of_run_dicts)
        
        model_run_stepdict_list=self.build_stepdict_list(stepcount=self.stepcount,threshcutstep=2,skipstep0=0,bestshare_list=[])
        saveqdumper=SaveQDumper(self.address)
        saveqdumper.start()
        for i,stepdict in enumerate(model_run_stepdict_list):
            
            self.logger.debug(f'i:{i}, stepdict:{stepdict}')
            #stepfolders=stepdict['stepfolders']
            try:
                self.logger.debug(f'i:{i},stepdict:{stepdict}')
                if 'variations' in stepdict:
                    list_of_run_dicts=self.generate_rundicts_from_variations()
                    runmasterresult=self.runmaster(list_of_run_dicts)
                    #self.logger.info(f'step#:{i} completed, runmasterresult:{runmasterresult}')
                else:
                    resultslist=[]

                    for functup in stepdict['functions']:
                        args=functup[1]
                        if args==[]:
                            args=[resultslist[-1]]
                        kwargs=functup[2]
                        result=functup[0](*args,**kwargs)
                        resultslist.append(result)
                    list_of_run_dicts=resultslist[-1]
                    self.logger.debug(f'step:{i} len(list_of_run_dicts):{len(list_of_run_dicts)}')
                    #self.rundict_advance_path(list_of_run_dicts,i,stepfolders)
                    runmasterresult=self.runmaster(list_of_run_dicts)
                self.logger.info(f'step#:{i} completed, runmasterresult:{runmasterresult}')
            except:
                self.logger.exception(f'i:{i},stepdict:{stepdict}')
                assert False,'halt'
                
                
                
    def runmaster(self,list_of_run_dicts):
        self.logger.debug(f'len(list_of_run_dicts):{len(list_of_run_dicts)}')
        jobqfiller=JobQFiller(list_of_run_dicts,self.address)
        #jobqfiller.start()
        #jobqfiller.join()
        jobqfiller.run()
        self.savecheck(list_of_run_dicts):
        return
    
    
    
    
    
    
    
    
    def savecheck(self,list_of_run_dicts):
        pathlist=[run_dict['savepath'] for run_dict in list_of_run_dicts][::-1] # reverse the order so the first item is checked first by pop()
        while pathlist:
            path=pathlist.pop()
            if not os.path.exists(path):
                pathlist.append(path)
                sleep(5)
            else:
                self.logger.debug(f'savecheck-path exists len(pathlist):{len(pathlist)}, path:{path}')
        return
                
        
           

if __name__=="__main__":

    #import mycluster
   
    
    RunNode()





