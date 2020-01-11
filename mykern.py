import multiprocessing
#import traceback
from copy import deepcopy
from typing import List
import os
from time import strftime, sleep
import datetime
import pickle
import numpy as np
#from numba import jit
from scipy.optimize import minimize
from sklearn.linear_model import LogisticRegression
import logging

#import logging.config
import yaml
import psutil

class kNdtool:
    """kNd refers to the fact that there will be kernels in kernels in these estimators

    """

    def __init__(self,savedir=None,myname=None):
        self.name=myname
        self.cores=int(psutil.cpu_count(logical=False)-1)
        #with open(os.path.join(os.getcwd(),'logconfig.yaml'),'rt') as f:
        #    configfile=yaml.safe_load(f.read())
        logging.basicConfig(level=logging.INFO)
        
        handlername=f'mykern-{self.name}.log'
        print(f'handlername:{handlername}')
        #below assumes it is a node if it has a name, so saving the node's log to the main cluster directory not the node's save directory
        if not self.name==None:
            handler=logging.FileHandler(os.path.join(savedir,'..',handlername))
        else:
            handler=logging.FileHandler(os.path.join(os.getcwd(),handlername))
        
        #self.logger = logging.getLogger('mkLogger')
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(handler)
        
        if savedir==None:
            savedir=os.getcwd()
        self.savedirectory=savedir

    
    def return_param_name_and_value(self,fixed_or_free_paramdict,modeldict):
        params={}
        paramlist=[key for key,val in modeldict['hyper_param_form_dict'].items()]
        for param in paramlist:
            paramdict=fixed_or_free_paramdict[param]
            form=paramdict['fixed_or_free']
            const=paramdict['const']
            start,end=paramdict['location_idx']
            
            value=fixed_or_free_paramdict[f'{form}_params'][start:end]
            if const=='non-neg':
                const=f'{const}'+':'+f'{np.exp(value)}'
            params[param]={'value':value,'const':const}
        return params
    
    
    def pull_value_from_fixed_or_free(self,param_name,fixed_or_free_paramdict,transform=None):
        if transform==None:
            transform=1
        if transform=='no':
            transform=0
        start,end=fixed_or_free_paramdict[param_name]['location_idx']
        if fixed_or_free_paramdict[param_name]['fixed_or_free']=='fixed':
            the_param_values=fixed_or_free_paramdict['fixed_params'][start:end]#end already includes +1 to make range inclusive of the end value
        if fixed_or_free_paramdict[param_name]['fixed_or_free']=='free':
            the_param_values=fixed_or_free_paramdict['free_params'][start:end]#end already includes +1 to make range inclusive of the end value
        if transform==1:
            if fixed_or_free_paramdict[param_name]['const']=='non-neg':#transform variable with e^(.) if there is a non-negative constraint
                the_param_values=np.exp(the_param_values)
        return the_param_values

    def setup_fixed_or_free(self,model_param_formdict,param_valdict):
        '''takes a dictionary specifying fixed or free and a dictionary specifying starting (if free) or
        fixed (if fixed) values
        returns 1 array and a dict
            free_params 1 dim np array of the starting parameter values in order,
                outside the dictionary to pass to optimizer
            fixed_params 1 dim np array of the fixed parameter values in order in side the dictionary
            fixed_or_free_paramdict a dictionary for each parameter (param_name) with the following key:val
                fixed_or_free:'fixed' or 'free'
                location_idx: the start and end location for parameters of param_name in the appropriate array,
                    notably end location has 1 added to it, so python indexing will correctly include the last value.
                fixed_params:array of fixed params
                Once inside optimization, the following will be added
                free_params:array of free params or string:'outside' if the array has been removed to pass to the optimizer
        '''
        fixed_params=np.array([]);free_params=np.array([]);fixed_or_free_paramdict={}
        #build fixed and free vectors of hyper-parameters based on hyper_param_formdict
        print(f'param_valdict:{param_valdict}')
        for param_name,param_form in model_param_formdict.items():
            param_feature_dict={}
            param_val=param_valdict[param_name]
            #print('param_val',param_val)
            #print('param_form',param_form)
            assert param_val.ndim==1,"values for {} have not ndim==1".format(param_name)
            if param_form=='fixed':
                param_feature_dict['fixed_or_free']='fixed'
                param_feature_dict['const']='fixed'
                param_feature_dict['location_idx']=(len(fixed_params),len(fixed_params)+len(param_val))
                    #start and end indices, with end already including +1 to make python slicing inclusive of end in start:end
                fixed_params=np.concatenate([fixed_params,param_val],axis=0)
                fixed_or_free_paramdict[param_name]=param_feature_dict
            elif param_form=='free':
                param_feature_dict['fixed_or_free']='free'
                param_feature_dict['const']='free'
                param_feature_dict['location_idx']=(len(free_params),len(free_params)+len(param_val))
                    #start and end indices, with end already including +1 to make python slicing inclusive of end in start:end
                free_params=np.concatenate([free_params,param_val],axis=0)
                fixed_or_free_paramdict[param_name]=param_feature_dict
            else:
                param_feature_dict['fixed_or_free']='free'
                param_feature_dict['const']=param_form
                param_feature_dict['location_idx']=(len(free_params),len(free_params)+len(param_val))
                    #start and end indices, with end already including +1 to make python slicing inclusive of end in start:end
                free_params=np.concatenate([free_params,param_val],axis=0)
                fixed_or_free_paramdict[param_name]=param_feature_dict
        fixed_or_free_paramdict['free_params']='outside'
        fixed_or_free_paramdict['fixed_params'] = fixed_params
        
        print(f'setup_fixed_or_free_paramdict:{fixed_or_free_paramdict}')
        return free_params,fixed_or_free_paramdict

    
    def makediffmat_itoj(self,xin,xpr):
        diffs= np.expand_dims(xin, axis=1) - np.expand_dims(xpr, axis=0)#should return ninXnoutXp if xin an xpr were ninXp and noutXp
        #print('type(diffs)=',type(diffs))
        return diffs



    def MY_KDE_gridprep_smalln(self,m,p):
        """creates a grid with all possible combinations of m=n^p (kerngrid not nin or nout) evenly spaced values from -3 to 3.
        """
        agrid=np.linspace(-3,3,m)[:,None] #assuming variables have been standardized
        #pgrid=agrid.copy()
        for idx in range(p-1):
            pgrid=np.concatenate([np.repeat(agrid,m**(idx+1),axis=0),np.tile(pgrid,[m,1])],axis=1)
            #outtup=()
            #pgrid=np.broadcast_to(np.linspace(-3,3,m),)
        return pgrid

    def prep_out_grid(self,xkerngrid,ykerngrid,xdata_std,ydata_std,modeldict,xpr=None):
        '''#for small data, pre-create the 'grid'/out data
        no big data version for now
        '''
        if modeldict['regression_model']=='logistic':
            if type(ykerngrid) is int:
                print(f'overriding modeldict:ykerngrid:{ykerngrid} to {"no"} b/c logisitic regression')
                ykerngrid='no'
        ykerngrid_form=modeldict['ykerngrid_form']
        if xpr is None:
            xpr=xdata_std
            #print('1st xpr.shape',xpr.shape)
            
            self.predict_self_without_self='yes'
        elif not xpr.shape==xdata_std.shape: 
            self.predict_self_without_self='n/a'
        elif not np.allclose(xpr,xdata_std):
            self.predict_self_without_self='n/a'
        if type(ykerngrid) is int and xkerngrid=="no":
            yout=self.generate_grid(ykerngrid_form,ykerngrid)#will broadcast later
            self.nout=ykerngrid
        if type(xkerngrid) is int:#this maybe doesn't work yet
            self.logger.warning("xkerngrid is not fully developed")
            self.nout=ykerngrid
            xpr=self.MY_KDE_gridprep_smalln(kerngrid,self.p)
            assert xpr.shape[1]==self.p,'xpr has wrong number of columns'
            assert xpr.shape[0]==kerngrid**self.p,'xpr has wrong number of rows'
            yxpr=self.MY_KDE_gridprep_smalln(kerngrid,self.p+1)
            assert yxpr.shape[1]==self.p+1,'yxpr has wrong number of columns'
            assert yxpr.shape[0]==kerngrid**(self.p+1),'yxpr has {} rows not {}'.format(yxpr.shape[0],kerngrid**(self.p+1))
        if xkerngrid=='no'and ykerngrid=='no':
            self.nout=self.nin
            yout=ydata_std
        #print('2nd xpr.shape',xpr.shape)
        #print('xdata_std.shape',xdata_std.shape)
        return xpr,yout
    
    def generate_grid(self,form,count):
        if form[0]=='even':
            gridrange=form[1]
            return np.linspace(-gridrange,gridrange,count)
        if form[0]=='exp':
            assert count%2==1,f'ykerngrid(={count}) must be odd for ykerngrid_form:exp'
            gridrange=form[1]
            log_gridrange=np.log(gridrange+1)
            log_grid=np.linspace(0,log_gridrange,(count+2)//2)
            halfgrid=np.exp(log_grid[1:])-1
            return np.concatenate((-halfgrid[::-1],np.array([0]),halfgrid),axis=0)
            
    
    def standardize_yx(self,xdata,ydata):
        self.xmean=np.mean(xdata,axis=0)
        self.ymean=np.mean(ydata,axis=0)
        self.xstd=np.std(xdata,axis=0)
        self.ystd=np.std(ydata,axis=0)
        standard_x=(xdata-self.xmean)/self.xstd
        standard_y=(ydata-self.ymean)/self.ystd
        return standard_x,standard_y

    def standardize_yxtup(self,yxtup_list,val_yxtup_list=None):
        #yxtup_list=deepcopy(yxtup_list_unstd)
        all_y=[ii for i in yxtup_list for ii in i[0]]
        all_x=[ii for i in yxtup_list for ii in i[1]]
        self.xmean=np.mean(all_x,axis=0)
        self.ymean=np.mean(all_y,axis=0)
        self.xstd=np.std(all_x,axis=0)
        self.ystd=np.std(all_y,axis=0)
        tupcount=len(yxtup_list)#should be same as batchcount
        yxtup_list_std=[]
        for i in range(tupcount):
            ystd=(yxtup_list[i][0] - self.ymean) / self.ystd
            xstd=(yxtup_list[i][1] - self.xmean) / self.xstd
            yxtup_list_std.append((ystd,xstd))
        if not val_yxtup_list==None:
            val_yxtup_list_std=[]
            val_tupcount=len(val_yxtup_list)
            for i in range(val_tupcount):
                val_ystd=(val_yxtup_list[i][0] - self.ymean) / self.ystd
                val_xstd=(val_yxtup_list[i][1] - self.xmean) / self.xstd
                val_yxtup_list_std.append((val_ystd,val_xstd))
        else: 
            val_yxtup_list_std=None
        return yxtup_list_std,val_yxtup_list_std


    def do_KDEsmalln(self,diffs,bw,modeldict):
        """estimate the density items in onediffs. collapse via products if dimensionality is greater than 2
        first 2 dimensions of onediffs must be ninXnout
        """ 
        assert diffs.shape==bw.shape, "diffs is shape:{} while bw is shape:{}".format(diffs.shape,bw.shape)
        allkerns=self.gkernh(diffs, bw)
        second_to_last_axis=allkerns.ndim-2
        normalization=modeldict['product_kern_norm']
        if normalization =='self':
            allkerns_sum=np.ma.sum(allkerns,axis=second_to_last_axis)#this should be the nout axis
            allkerns=allkerns/self.ma_broadcast_to(np.ma.expand_dims(allkerns_sum,second_to_last_axis),allkerns.shape)
            
            # collapse just nin dim or both lhs dims?
        if normalization =="own_n":
            allkerns=allkerns/np.ma.expand_dims(np.ma.count(allkerns,axis=second_to_last_axis),second_to_last_axis)#1 should be the nout axis
        if modeldict['regression_model']=='NW-rbf' or modeldict['regression_model']=='NW-rbf2':
            if allkerns.ndim>3:
                for i in range((allkerns.ndim-3),0,-1):
                    assert allkerns.ndim>3, "allkerns is being collapsed via rbf on rhs " \
                                            "but has {} dimensions instead of ndim>3".format(allkerns.ndim)
                    allkerns=np.ma.power(np.ma.sum(np.ma.power(allkerns,2),axis=allkerns.ndim-1),0.5)#collapse right most dimension, so if the two items in the 3rd dimension\\
        if modeldict['regression_model']=='NW':
            if allkerns.ndim>3:
                for i in range((allkerns.ndim-3),0,-1):
                    assert allkerns.ndim>3, "allkerns is being collapsed via product on rhs " \
                                            "but has {} dimensions instead of ndim>3".format(allkerns.ndim)
                    allkerns=np.ma.product(allkerns,axis=allkerns.ndim-1)#collapse right most dimension, so if the two items in the 3rd dimension\\
        return np.ma.sum(allkerns,axis=0)/self.nin#collapsing across the nin kernels for each of nout    
        
    def ma_broadcast_to(self, maskedarray,tup):
            initial_mask=np.ma.getmask(maskedarray)
            broadcasted_mask=np.broadcast_to(initial_mask,tup)
            broadcasted_array=np.broadcast_to(maskedarray,tup)
            return np.ma.array(broadcasted_array, mask=broadcasted_mask)
            
    def sort_then_saveit(self,mse_param_list,modeldict,filename):
        
        fullpath_filename=os.path.join(self.savedirectory,filename)
        mse_list=[i[0] for i in mse_param_list]
        minmse=min(mse_list)
        fof_param_dict_list=[i[1] for i in mse_param_list]
        bestparams=fof_param_dict_list[mse_list.index(minmse)]
        savedict={}
        savedict['mse']=minmse
        #savedict['xdata']=self.xdata
        #savedict['ydata']=self.ydata
        savedict['params']=bestparams
        savedict['modeldict']=modeldict
        now=strftime("%Y%m%d-%H%M%S")
        savedict['when_saved']=now
        savedict['datagen_dict']=self.datagen_dict
        try:#this is only relevant after optimization completes
            savedict['minimize_obj']=self.minimize_obj
        except:
            pass
        for i in range(10):
            try: 
                with open(fullpath_filename,'rb') as modelfile:
                    modellist=pickle.load(modelfile)
                break
            except FileNotFoundError:
                modellist=[]
                break
            except:
                sleep(0.1)
                if i==9:
                    self.logger.exception(f'error in {__name__}')
                    modellist=[]
        #print('---------------success----------')
        if len(modellist)>0:
            lastsavetime=modellist[-1]['when_saved']
            runtime=datetime.datetime.strptime(now,"%Y%m%d-%H%M%S")-datetime.datetime.strptime(lastsavetime,"%Y%m%d-%H%M%S")
            print(f'time between saves for {self.name} is {runtime}')
        modellist.append(savedict)
        
        for i in range(10):
            try:
                with open(fullpath_filename,'wb') as thefile:
                    pickle.dump(modellist,thefile)
                print(f'saved to {fullpath_filename} at about {strftime("%Y%m%d-%H%M%S")} with mse={minmse}')
                break
            except:
                if i==9:
                    print(f'mykern.py could not save to {fullpath_filename} after {i+1} tries')
        return
    
    #def validate_KDEreg(self,yin,yout,xin,xpr,modeldict,fixed_or_free_paramdict)):
        
    
    def MY_KDEpredict(self,yin,yout,xin,xpr,modeldict,fixed_or_free_paramdict):
        """moves free_params to first position of the obj function, preps data, and then runs MY_KDEreg to fit the model
            then returns MSE of the fit 
        Assumes last p elements of free_params are the scale parameters for 'el two' approach to
        columns of x.
        """
        
        try:
            lossfn=modeldict['loss_function']
        except KeyError:
            lossfn='mse'
        iscrossmse=lossfn[0:8]=='crossmse'
        
        max_bw_Ndiff=modeldict['max_bw_Ndiff']
        #pull x_bandscale parameters from the appropriate location and appropriate vector
        x_bandscale_params=self.pull_value_from_fixed_or_free('x_bandscale',fixed_or_free_paramdict)
        y_bandscale_params=self.pull_value_from_fixed_or_free('y_bandscale',fixed_or_free_paramdict)
        p=x_bandscale_params.shape[0]
        assert self.p==p,\
            "p={} but x_bandscale_params.shape={}".format(self.p,x_bandscale_params.shape)

        if modeldict['Ndiff_bw_kern']=='rbfkern':
            xin_scaled=xin*x_bandscale_params
            #print('xin_scaled.shape',xin_scaled.shape)
            xpr_scaled=xpr*x_bandscale_params
            #print('xpr_scaled.shape',xpr_scaled.shape)
            yin_scaled=yin*y_bandscale_params
            yout_scaled=yout*y_bandscale_params
            y_onediffs=self.makediffmat_itoj(yin_scaled,yout_scaled)
            y_Ndiffs=self.makediffmat_itoj(yin_scaled,yin_scaled)
            onediffs_scaled_l2norm=np.power(np.sum(np.power(self.makediffmat_itoj(xin_scaled,xpr_scaled),2),axis=2),.5)
            Ndiffs_scaled_l2norm=np.power(np.sum(np.power(self.makediffmat_itoj(xin_scaled,xin_scaled),2),axis=2),.5)
            assert onediffs_scaled_l2norm.shape==(xin.shape[0],xpr.shape[0]),f'onediffs_scaled_l2norm has shape:{onediffs_scaled_l2norm.shape} not shape:({self.nin},{self.npr})'

            diffdict={}
            diffdict['onediffs']=onediffs_scaled_l2norm
            diffdict['Ndiffs']=Ndiffs_scaled_l2norm
            ydiffdict={}
            ydiffdict['onediffs']=np.broadcast_to(y_onediffs[:,:,None],y_onediffs.shape+(self.npr,))
            ydiffdict['Ndiffs']=np.broadcast_to(y_Ndiffs[:,:,None],y_Ndiffs.shape+(self.npr,))
            diffdict['ydiffdict']=ydiffdict


        if modeldict['Ndiff_bw_kern']=='product':
            onediffs=makediffmat_itoj(xin,xpr)#scale now? if so, move if...='rbfkern' down 
            #predict
            yhat=self.MY_NW_KDEreg(yin_scaled,xin_scaled,xpr_scaled,yout_scaled,fixed_or_free_paramdict,diffdict,modeldict)[0]
            #not developed yet
        
        xbw = self.NdiffBWmaker(max_bw_Ndiff, fixed_or_free_paramdict, diffdict, modeldict,'x')
        ybw = self.NdiffBWmaker(max_bw_Ndiff, fixed_or_free_paramdict, diffdict['ydiffdict'],modeldict,'y')

        #print('xbw',xbw)
        #print('ybw',ybw)
        
        
        '''xbwmaskcount=np.ma.count_masked(xbw)
        print('xbwmaskcount',xbwmaskcount)
        print('np.ma.getmask(xbw)',np.ma.getmask(xbw))
        
        ybwmaskcount=np.ma.count_masked(ybw)
        print('ybwmaskcount',ybwmaskcount)
        print('np.ma.getmask(ybw)',np.ma.getmask(ybw))'''

        hx=self.pull_value_from_fixed_or_free('outer_x_bw', fixed_or_free_paramdict)
        hy=self.pull_value_from_fixed_or_free('outer_y_bw', fixed_or_free_paramdict)
                
        xbw=xbw*hx
        
        
        if modeldict['regression_model']=='logistic':
            xonediffs=diffdict['onediffs']
            prob_x = self.do_KDEsmalln(xonediffs, xbw, modeldict)
            
            yhat_tup=self.kernel_logistic(prob_x,xin,yin)
            yhat_std=yhat_tup[0]
            crosserrors=yhat_tup[1]
            
        if modeldict['regression_model'][0:2]=='NW':
            ybw=ybw*hy
            xonediffs=diffdict['onediffs']
            yonediffs=diffdict['ydiffdict']['onediffs']
            assert xonediffs.ndim==2, "xonediffs have ndim={} not 2".format(xonediffs.ndim)
            ykern_grid=modeldict['ykern_grid'];xkern_grid=modeldict['xkern_grid']
            if True:#type(ykern_grid) is int and xkern_grid=='no':
                xonedifftup=xonediffs.shape[:-1]+(self.nout,)+(xonediffs.shape[-1],)
                xonediffs_stack=np.broadcast_to(np.expand_dims(xonediffs,len(xonediffs.shape)-1),xonedifftup)
                xbw_stack=np.broadcast_to(np.ma.expand_dims(xbw,len(xonediffs.shape)-1),xonedifftup)
            newaxis=len(yonediffs.shape)
            yx_onediffs_endstack=np.ma.concatenate((np.expand_dims(xonediffs_stack,newaxis),np.expand_dims(yonediffs,newaxis)),axis=newaxis)
            yx_bw_endstack=np.ma.concatenate((np.ma.expand_dims(xbw_stack,newaxis),np.ma.expand_dims(ybw,newaxis)),axis=newaxis)
            #print('type(xonediffs)',type(xonediffs),'type(xbw)',type(xbw),'type(modeldict)',type(modeldict))
            
            prob_x = self.do_KDEsmalln(xonediffs, xbw, modeldict)
            prob_yx = self.do_KDEsmalln(yx_onediffs_endstack, yx_bw_endstack,modeldict)#do_KDEsmalln implements product \\
                #kernel across axis=2, the 3rd dimension after the 2 diensions of onediffs. endstack refers to the fact \\
                #that y and x data are stacked in dimension 2 and do_kdesmall_n collapses them via the product of their kernels.
            #print('type(prob_x)',type(prob_x),'type(prob_yx)',type(prob_x))
            #print(prob_x,prob_yx)
            KDEregtup = self.my_NW_KDEreg(prob_yx,prob_x,yout_scaled,modeldict)
            yhat_raw=KDEregtup[0]
            crosserrors=KDEregtup[1]
            yhat_std=yhat_raw*y_bandscale_params**-1#remove the effect of any parameters applied prior to using y.

        yhat_un_std=yhat_std*self.ystd+self.ymean
        
        #print(f'yhat_un_std:{yhat_un_std}')
<<<<<<< HEAD
        if not iscrossmse:#lossfn=='mse'
            return (yhat_un_std,None)
        if iscrossmse:
            #print('yhat_un_std',yhat_un_std)
            crosserrors_unstd=crosserrors*self.ystd
            #print('crosserrors_unstd',crosserrors_unstd)    
            return (yhat_un_std,crosserrors_unstd)
=======
        if not iscrossmse:
            return (yhat_un_std,'no_cross_errors')
        if iscrossmse:
            return (yhat_un_std,cross_errors*self.ystd)
>>>>>>> cccf8cf2bf0e09364c138f34797e180e362879db
        
    def kernel_logistic(self,prob_x,xin,yin):
        lossfn=modeldict['loss_function']
        iscrossmse=lossfn[0:8]=='crossmse'
                      
        for i in range(prob_x.shape[-1]):
            xin_const=np.concatenate(np.ones((xin.shape[0],1),xin,axis=1))
            yhat_i=LogisticRegression().fit(xin_const,yin,prob_x[...,i]).predict(xin)
            yhat_std.extend(yhat_i[i])
            crosserrors.extend(yhat_i)#list with ii on dim0
        crosserrors=np.masked_array(crosserrors,mask=np.eye(yin.shape[0])).T#to put ii back on dim 1
        yhat=np.array(yhat_std)                             
        if not iscrossmse:
            return (yhat,'no_cross_errors')
        if iscrossmse:
            if len(lossfn)>8:
                cross_exp=float(lossfn[8:])
                wt_stack=prob_x**cross_exp
            
            crosserrors=(yhat[None,:]-yout[:,None])#this makes dim0=nout,dim1=nin
            crosswt_stack=wt_stack/np.ma.expand_dims(np.ma.sum(wt_stack,axis=1),axis=1)
            wt_crosserrors=np.ma.sum(crosswt_stack*crosserrors,axis=1)#weights normalized to sum to 1, then errors summed to 1 per nin
            return (yhat,wt_crosserrors)

    def my_NW_KDEreg(self,prob_yx,prob_x,yout,modeldict):
        """returns predited values of y for xpredict based on yin, xin, and modeldict
        """
        lossfn=modeldict['loss_function']
        iscrossmse=lossfn[0:8]=='crossmse'
            
        yout_axis=len(prob_yx.shape)-2#-2 b/c -1 for index form vs len count form and -1 b/c second to last dimensio is what we seek.
        
        #prob_yx_sum=np.broadcast_to(np.ma.expand_dims(np.ma.sum(prob_yx,axis=yout_axis),yout_axis),prob_yx.shape)
        #cdfnorm_prob_yx=prob_yx/prob_yx_sum
        #cdfnorm_prob_yx=prob_yx#dropped normalization
        #prob_x_sum=np.broadcast_to(np.ma.expand_dims(np.ma.sum(prob_x, axis=yout_axis),yout_axis),prob_x.shape)
        #cdfnorm_prob_x = prob_x / prob_x_sum
        #cdfnorm_prob_x = prob_x#dropped normalization
        
        yout_stack=self.ma_broadcast_to(np.ma.expand_dims(yout,1),(self.nout,self.npr))
        prob_x_stack_tup=prob_x.shape[:-1]+(self.nout,)+(prob_x.shape[-1],)
        prob_x_stack=self.ma_broadcast_to(np.ma.expand_dims(prob_x,yout_axis),prob_x_stack_tup)
        NWnorm=modeldict['NWnorm']
                
        if modeldict['regression_model']=='NW-rbf2':
            wt_stack=np.ma.power(np.ma.power(prob_yx,2)-np.ma.power(prob_x_stack,2),0.5)
            if NWnorm=='across':
                wt_stack=wt_stack/np.ma.expand_dims(np.ma.sum(wt_stack,axis=1),axis=1)
            yhat=np.ma.sum(yout_stack*wt_stack,axis=yout_axis)
        else:
            wt_stack=prob_yx/prob_x_stack
            if NWnorm=='across':
                wt_stack=wt_stack/np.ma.expand_dims(np.ma.sum(wt_stack,axis=1),axis=1)
            yhat=np.ma.sum(yout_stack*wt_stack,axis=yout_axis)#sum over axis=0 collapses across nin for each nout
            yhatmaskscount=np.ma.count_masked(yhat)
            if yhatmaskscount>0:print('in my_NW_KDEreg, yhatmaskscount:',yhatmaskscount)
        #print(f'yhat:{yhat}')
        
        #self.logger.info(f'type(yhat):{type(yhat)}. yhat: {yhat}')
        if not iscrossmse:
            return (yhat,'no_cross_errors')
        if iscrossmse:
            if len(lossfn)>8:
                cross_exp=float(lossfn[8:])
                wt_stack=wt_stack**cross_exp
            
            crosserrors=(yhat[None,:]-yout[:,None])#this makes dim0=nout,dim1=nin
            crosswt_stack=wt_stack/np.ma.expand_dims(np.ma.sum(wt_stack,axis=1),axis=1)
            wt_crosserrors=np.ma.sum(crosswt_stack*crosserrors,axis=1)#weights normalized to sum to 1, then errors summed to 1 per nin
            return (yhat,wt_crosserrors)
    
    def predict_tool(self,xpr,fixed_or_free_paramdict,modeldict):
        """
        """
        xpr=(xpr-self.xmean)/self.xstd
        
        self.prediction=MY_KDEpredictMSE(self, free_params, batchdata_dict, modeldict, fixed_or_free_paramdict,predict=None)
        
        return self.prediction.yhat

    def MY_KDEpredictMSE(self, free_params, batchdata_dict, modeldict, fixed_or_free_paramdict,predict=None):
        #predict=1 or yes signals that the function is not being called for optimization, but for prediction.
        if predict==None or predict=='no':
            predict=0
        if predict=='yes':
            predict=1
        if  type(fixed_or_free_paramdict['free_params']) is str and fixed_or_free_paramdict['free_params'] =='outside':  
            self.call_iter += 1  # then it must be a new call during optimization

        #batchcount = self.datagen_dict['batchcount']
        batchcount = len(batchdata_dict['yintup'])
        #print(f'batchcount:{batchcount}')
        fixed_or_free_paramdict['free_params'] = free_params
        # print(f'free_params added to dict. free_params:{free_params}')

        try:
            lossfn=modeldict['loss_function']
        except KeyError:
            print(f'loss_function not found in modeldict')
            lossfn='mse'
        iscrossmse=lossfn[0:8]=='crossmse'

        y_err_tup = ()

        arglistlist=[]
        for batch_i in range(batchcount):
            
            arglist=[]
            arglist.append(batchdata_dict['yintup'][batch_i])
            arglist.append(batchdata_dict['youttup'][batch_i])
            arglist.append(batchdata_dict['xintup'][batch_i])
            arglist.append(batchdata_dict['xprtup'][batch_i])

            arglist.append(modeldict)
            arglist.append(fixed_or_free_paramdict)
            arglistlist.append(arglist)

        process_count=1#self.cores
        if process_count>1 and batchcount>1:
            with multiprocessing.Pool(processes=process_count) as pool:
<<<<<<< HEAD
                yhat_unstd_tup=pool.map(self.MPwrapperKDEpredict,arglistlist)
=======
                yhat_unstd_outtup_list=pool.map(self.MPwrapperKDEpredict,arglistlist)
>>>>>>> cccf8cf2bf0e09364c138f34797e180e362879db
                sleep(2)
                pool.close()
                pool.join()
        else:
<<<<<<< HEAD
            yhat_unstd_tup=[]
            for i in range(batchcount):
                yhat_unst_i=self.MPwrapperKDEpredict(arglistlist[i])
                #print('type(yhat_unst_i)',type(yhat_unst_i))
                #try: print(yhat_unst_i.shape)
                #except:pass
                yhat_unstd_tup.append(yhat_unst_i)
        #if iscrossmse:
        #print('len(yhat_unstd_tup)',len(yhat_unstd_tup))
        yhat_unstd=[];crosserrors=[]
        for batch in yhat_unstd_tup:
            #print('yhat unstd batch',batch)
            yhat_unstd.append(batch[0])
            crosserrors.append(batch[1])
            
        #yhat_unstd,crosserrors=zip(*yhat_unstd)
=======
            yhat_unstd_outtup_list=[]
            for i in range(batchcount):
                result_tup=self.MPwrapperKDEpredict(arglistlist[i])
                #self.logger.info(f'result_tup: {result_tup}')
                yhat_unstd_outtup_list.append(result_tup)
        #self.logger.info(f'yhat_unstd_outtup_list: {yhat_unstd_outtup_list}')
        yhat_unstd,crosserrors=zip(*yhat_unstd_outtup_list)
        
>>>>>>> cccf8cf2bf0e09364c138f34797e180e362879db
        #print(f'after mp.pool,yhat_unstd has shape:{np.shape(yhat_unstd)}')
        

                
        if modeldict['loss_function']=='batch_crossval':
            ybatch=[]
            for i in range(batchcount):
                ycross_j=[]
                for j,yxvartup in enumerate(self.datagen_obj.yxtup_list):
                    if not j==i:
                        ycross_j.append(yxvartup[0])
                ybatch.append(np.concatenate(ycross_j,axis=0))
                
                
        else:
            ybatch=[tup[0] for tup in self.datagen_obj.yxtup_list]#the original yx data is a list of tupples
        for batch_i in range(batchcount):
            y_batch_i=ybatch[i]
            y_err = y_batch_i - yhat_unstd[batch_i]
            y_err_tup = y_err_tup + (y_err,)


        all_y_err = np.ma.concatenate(y_err_tup,axis=0)

        
        #print('all_y_err',all_y_err)
        if iscrossmse:
            all_y_err=np.ma.concatenate([all_y_err,np.ravel(crosserrors)],axis=0)
        mse = np.ma.mean(np.ma.power(all_y_err, 2))
        maskcount=np.ma.count_masked(all_y_err)

        assert maskcount==0,print(f'{maskcount} masked values found in all_y_err')
        
        if predict==0:
            self.mse_param_list.append((mse, deepcopy(fixed_or_free_paramdict)))
            # self.return_param_name_and_value(fixed_or_free_paramdict,modeldict)
            self.fixed_or_free_paramdict = fixed_or_free_paramdict
            t_format = "%Y%m%d-%H%M%S"
            self.iter_start_time_list.append(strftime(t_format))

            if self.call_iter == 3:
                tdiff = np.abs(
                    datetime.datetime.strptime(self.iter_start_time_list[-1], t_format) - datetime.datetime.strptime(
                        self.iter_start_time_list[-2], t_format))
                self.save_interval = int(max([15 - np.round(np.log(tdiff.total_seconds() + 1) ** 3, 0),
                                              1]))  # +1 to avoid negative and max to make sure save_interval doesn't go below 1
                print(f'save_interval changed to {self.save_interval}')

            if self.call_iter % self.save_interval == 0:
                self.sort_then_saveit(self.mse_param_list[-self.save_interval * 2:], modeldict, 'model_save')


        # assert np.ma.count_masked(yhat_un_std)==0,"{}are masked in yhat of yhatshape:{}".format(np.ma.count_masked(yhat_un_std),yhat_un_std.shape)

        return mse

    def MPwrapperKDEpredict(self,arglist):
        #print(f'arglist inside wrapper is:::::::{arglist}')
        yin=arglist[0]
        yout=arglist[1]
        xin=arglist[2]
        xpr=arglist[3]
        modeldict=arglist[4]
        fixed_or_free_paramdict=arglist[5]
        KDEpredict_tup=self.MY_KDEpredict(yin, yout, xin, xpr, modeldict, fixed_or_free_paramdict)
        #print('type(KDEpredict_tup)',type(KDEpredict_tup))
        #try:print(KDEpredict_tup[0].shape)
        #except:pass
        return KDEpredict_tup
    
    def prep_KDEreg(self,datagen_obj,modeldict,param_valdict,predict=None):
        if predict==None:
            predict=0
        
        #free_params,args_tuple=self.prep_KDEreg(datagen_obj,modeldict,param_valdict)

        self.datagen_obj=datagen_obj
        
        model_param_formdict=modeldict['hyper_param_form_dict']
        xkerngrid=modeldict['xkern_grid']
        ykerngrid=modeldict['ykern_grid']
        max_bw_Ndiff=modeldict['max_bw_Ndiff']
        
        #build dictionary for parameters
        free_params,fixed_or_free_paramdict=self.setup_fixed_or_free(model_param_formdict,param_valdict)
        self.fixed_or_free_paramdict=fixed_or_free_paramdict
        if predict==1:
            self.fixed_or_free_paramdict['free_params']='predict'#instead of 'outside'
                
        #save and transform the data
        #self.xdata=datagen_obj.x;self.ydata=datagen_obj.y#this is just the first of the batches, if batchcount>1
        self.batchcount=datagen_obj.batchcount
        self.nin=datagen_obj.batch_n
        self.p=datagen_obj.param_count#p should work too
        #assert self.ydata.shape[0]==self.xdata.shape[0],'xdata.shape={} but ydata.shape={}'.format(xdata.shape,ydata.shape)

        #standardize x and y and save their means and std to self
        yxtup_list_std,val_yxtup_list_std = self.standardize_yxtup(datagen_obj.yxtup_list,datagen_obj.val_yxtup_list)
        #print('buildbatcdatadict')
        batchdata_dict=self.buildbatchdatadict(yxtup_list_std,xkerngrid,ykerngrid,modeldict)
        #print('for validation buildbatcdatadict')
        val_batchdata_dict=self.buildbatchdatadict(val_yxtup_list_std,xkerngrid,ykerngrid,modeldict)
        self.npr=len(batchdata_dict['xprtup'][0])
        print('self.npr',self.npr)
        #print('=======================')
        #print(f'batchdata_dict{batchdata_dict}')
        #print('=======================')
        #self.npr=xpr.shape[0]#probably redundant
        #self.yout=yout

        #pre-build list of masks
        self.Ndiff_list_of_masks_y=self.max_bw_Ndiff_maskstacker_y(self.npr,self.nout,self.nin,self.p,max_bw_Ndiff,modeldict)
        self.Ndiff_list_of_masks_x=self.max_bw_Ndiff_maskstacker_x(self.npr,self.nout,self.nin,self.p,max_bw_Ndiff,modeldict)
        
        #setup and run scipy minimize
        args_tuple=(batchdata_dict, modeldict, self.fixed_or_free_paramdict)
        val_args_tuple=(val_batchdata_dict, modeldict, self.fixed_or_free_paramdict)
        print(f'mykern modeldict:{modeldict}')
        
        return free_params,args_tuple,val_args_tuple
    
    
    def buildbatchdatadict(self,yxtup_list,xkerngrid,ykerngrid,modeldict):
        #load up the data for each batch into a dictionary full of tuples
        # with each tuple item containing data for a batch from 0 to batchcount-1
        batchcount=len(yxtup_list)
        #print('from buildbatchdatadict: batchcount: ',batchcount)
        #print('self.batchcount: ',self.batchcount)
        xintup = ()
        yintup = ()
        xprtup = ()
        youttup = ()
        if modeldict['loss_function']=='batch_crossval':
            xpri=[]
            for i in range(batchcount):
                xpricross_j=[]
                for j,yxvartup in enumerate(yxtup_list):
                    if not j==i:
                        xpricross_j.append(yxvartup[1])
                xpri_crossval_array=np.concatenate(xpricross_j,axis=0)
                    #print('xpri_crossval_array.shape',xpri_crossval_array.shape)
                xpri.append(xpri_crossval_array)
                
            
        else:
            xpri=[None]*batchcount #self.prep_out_grid will treat this as in-sample prediction
        for i in range(batchcount):
            xdata_std=yxtup_list[i][1]
            #print('xdata_std.shape: ',xdata_std.shape)
            ydata_std=yxtup_list[i][0]
            #print('xprii[i]',xpri[i])
            xpr_out_i,youti=self.prep_out_grid(xkerngrid,ykerngrid,xdata_std,ydata_std,modeldict,xpr=xpri[i])
            #print('xpr_out_i.shape',xpr_out_i.shape)
            xintup=xintup+(xdata_std,)
            yintup=yintup+(ydata_std,)
            xprtup=xprtup+(xpr_out_i,)
            youttup=youttup+(youti,)
            #print('xprtup[0].shape:',xprtup[0].shape)

        batchdata_dict={'xintup':xintup,'yintup':yintup,'xprtup':xprtup,'youttup':youttup}
        #print([f'{key}:{type(val)},{type(val[0])}' for key,val in batchdata_dict.items()])
        return batchdata_dict
    
class optimize_free_params(kNdtool):
    """"This is the method for iteratively running kernelkernel to optimize hyper parameters
    optimize dict contains starting values for free parameters, hyper-parameter structure(is flexible),
    and a model dict that describes which model to run including how hyper-parameters enter (quite flexible)
    speed and memory usage is a big goal when writing this. I pre-created masks to exclude the increasing
    list of centered data points. see mykern_core for an example and explanation of dictionaries.
    Flexibility is also a goal. max_bw_Ndiff is the deepest the model goes.
    ------------------
    attributes created
    self.n,self.p
    self.xdata,self.ydata contain the original data
    self.xdata_std, self.xmean,self.xstd
    self.ydata_std,self.ymean,self.ystd
    self.Ndiff_list_of_masks - a list of progressively higher dimension (len=nin)
        masks to broadcast(views) Ndiff to.
    """

    def __init__(self,datagen_obj,optimizedict,savedir=None,myname=None):
        self.call_iter=0#one will be added to this each time the outer MSE function is called by scipy.minimize
        self.mse_param_list=[]#will contain a tuple of  (mse, fixed_or_free_paramdict) at each call
        self.iter_start_time_list=[]
        self.save_interval=1
        self.datagen_dict=optimizedict['datagen_dict']
<<<<<<< HEAD
        self.name=myname
=======
        self.logger.info(f'optimizedict for {myname}:{optimizedict}')
        #Extract from optimizedict
        modeldict=optimizedict['modeldict'] 
>>>>>>> cccf8cf2bf0e09364c138f34797e180e362879db
        opt_settings_dict=optimizedict['opt_settings_dict']
        method=opt_settings_dict['method']
        opt_method_options=opt_settings_dict['options']
        '''mse_threshold=opt_settings_dict['mse_threshold']
        inherited_mse=optimizedict['mse']
        if inherited_mse<mse_threshold:
            print(f'optimization halted because inherited mse:{inherited_mse}<mse_threshold:{mse_threshold}')
            return'''
        
        #Extract from optimizedict
        modeldict=optimizedict['modeldict'] 
        
        param_valdict=optimizedict['hyper_param_dict']

        
        if savedir==None:
            savedir=os.getcwd()
        kNdtool.__init__(self,savedir=savedir,myname=myname)
        free_params,args_tuple,val_args_tuple=self.prep_KDEreg(datagen_obj,modeldict,param_valdict)
        self.minimize_obj=minimize(self.MY_KDEpredictMSE, free_params, args=args_tuple, method=method, options=opt_method_options)
        
        lastmse=self.mse_param_list[-1][0]
        lastparamdict=self.mse_param_list[-1][1]
        self.sort_then_saveit([[lastmse,lastparamdict]],modeldict,'model_save')
        #self.sort_then_saveit(self.mse_param_list[-self.save_interval*3:],modeldict,'final_model_save')
        self.sort_then_saveit(self.mse_param_list,modeldict,'final_model_save')
        print(f'lastparamdict:{lastparamdict}')
        

if __name__ == "__main__":

    import os
    import kernelcompare as kc
    import traceback
    import mykern

    # from importlib import reload
    networkdir = 'o:/public/dpatton/kernel'
    mydir = os.getcwd()
    test = kc.KernelCompare(directory=mydir)

    Ndiff_type_variations = ('modeldict:Ndiff_type', ['recursive', 'product'])
    max_bw_Ndiff_variations = ('modeldict:max_bw_Ndiff', [2])
    Ndiff_start_variations = ('modeldict:Ndiff_start', [1, 2])
    ykern_grid_variations = ('ykern_grid', [49])
    # product_kern_norm_variations=('modeldict:product_kern_norm',['self','own_n'])#include None too?
    # normalize_Ndiffwtsum_variations=('modeldict:normalize_Ndiffwtsum',['own_n','across'])
    optdict_variation_list = [Ndiff_type_variations, max_bw_Ndiff_variations,
                              Ndiff_start_variations]  # ,product_kern_norm_variations,normalize_Ndiffwtsum_variations]

    # the default datagen_dict as of 11/25/2019
    # datagen_dict={'batch_n':32,'batchcount':10, 'param_count':param_count,'seed':1, 'ftype':'linear', 'evar':1, 'source':'monte'}
    batch_n_variations = ('batch_n', [32])
    batchcount_variations = ('batchcount', [8])
    ftype_variations = ('ftype', ['linear', 'quadratic'])
    param_count_variations = ('param_count', [1, 2])
    datagen_variation_list = [batch_n_variations, batchcount_variations, ftype_variations, param_count_variations]
    testrun = test.prep_model_list(optdict_variation_list=optdict_variation_list,
                                   datagen_variation_list=datagen_variation_list, verbose=1)

    from random import shuffle

    #shuffle(testrun)
    # a_rundict=testrun[100]#this produced the Ndiff_exponent error for recursive Ndiff
    for idx in range(len(testrun)):
        print(f'~~~~~~~run number:{idx}`~~~~~~~')
        a_rundict = testrun[idx]
        print(f'a_rundict{a_rundict}')
        optimizedict = a_rundict['optimizedict']
        datagen_dict = a_rundict['datagen_dict']

        try:
            test.do_monte_opt(optimizedict, datagen_dict, force_start_params=0)
            test.open_condense_resave('model_save', verbose=0)
            test.merge_and_condense_saved_models(merge_directory=None, save_directory=None, condense=1, verbose=0)
        except:
            print('traceback for run', idx)
            self.logger.exception(f'error in {__name__}')
