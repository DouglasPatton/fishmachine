import os
import csv
import traceback
import numpy as np
import pickle
from time import sleep
import multiprocessing as mp
import geopandas as gpd


class DataTool():
    def __init__(self,):
        self.savedir=os.path.join(os.getcwd(),'data_tool')
        if not os.path.exists(self.savedir):
            os.mkdir(self.savedir)
        #self.filenamelist=['HUC12_PU_COMIDs_CONUS.csv','siteinfo.csv','surveydata.csv']
    
    #def getsqlfile(self,filename):
    #    con=sqlite3.connect(os.path.join(os.getcwd(),'fishfiles','catchments.sqlite'))
        
    def getNHDplus(self,):
        self.NHDvarlist=['COMID','HUC12','REACHCODE','TOHUC','Length']
        savefilename=os.path.join(self.savedir,'NHDplus.data')
        if os.path.exists(savefilename):
            try: 
                with open(savefilename, 'rb') as f:
                    self.NHDplus=pickle.load(f)
                print(f'opening {savefilename} with length:{len(self.NHDplus)} and type:{type(self.NHDplus)}')
                return
            except: 
                print(f"{savefilename} exists but could not open, rebuilding")
        
        filename=os.path.join(os.getcwd(),'fishfiles','huc12_pu_comids_conus.dbf')
        
        #dbf = gpd.GeoDataFrame.from_file(filename)
        print(f'starting read of {filename}')
        dbf=gpd.read_file(filename)
        print(f'opening {filename} with length:{len(dbf)} and type:{type(dbf)}')
        print('finished read of NHDplus')
        
        #self.dbf=dbf
        #self.NHDplus=[dbf[var].tolist() for var in varlist]
        self.NHDplus=dbf[self.NHDvarlist]
        
        try:
            with open(savefilename,'wb') as f:
                pickle.dump(self.NHDplus,f)
        except:
            print('problem saving NHDplus:')
            print(traceback.format_exc())
        
        
        
    def getdatafile(self,filename):
        thisdir=os.getcwd()
        datadir=os.path.join(thisdir,'fishfiles',filename)
        if os.path.exists(datadir):
            with open(datadir, 'r') as f:
                datadict=[row for row in csv.DictReader(f)]
        print(f'opening {filename} with length:{len(datadict)} and type:{type(datadict)}')
        keylist=[key for row in datadict for key,val in row.items()]
        return datadict

    def getfishdata(self,):
        self.fishsurveydata=self.getdatafile('surveydata.csv')

    def gethucdata(self,):
        self.getNHDplus

    def getsitedata(self,):
        self.sitedata=self.getdatafile('siteinfo.csv')
        
    def getfishhucs(self,):
        self.fishhucs=self.getdatafile('fishhucs.csv')

        
    def buildspecieslist(self,):
        specieslistpath=os.path.join(self.savedir,'specieslist')
        if os.path.exists(specieslistpath):
            try:
                with open(specieslistpath,'rb') as f:
                    speciestup=pickle.load(f)
                self.specieslist=speciestup[0]
                self.speciesoccurencelist=speciestup[1]
                self.speciescomidlist=speciestup[2]
                self.specieshuclist=speciestup[3]
                self.huclist=speciestup[4]
                self.huccomidlist=speciestup[5]
                self.specieshuclistidx=speciestup[6]
                print(f'opening {specieslistpath} with length:{len(speciestup)} and type:{type(speciestup)}')
                return
            except:
                print(f'buildspecieslist found {specieslistpath} but there was an error loading variables')
                print(traceback.format_exc())
        try:self.fishsurveydata
        except: self.getfishdata()
        (longlist,huclist,comidlist)=zip(*[(obs['genus_species'],obs['HUC'],obs['COMID']) for obs in self.fishsurveydata])
        shortlist=[];occurencelist=[];speciescomidlist=[];specieshuclist=[]
        shorthuclist=[];huccomidlist=[];specieshuclistidx=[]
        print('building specieslist')
        length=len(longlist)
        for idx,fish in enumerate(longlist):
            if idx%(length//33)==0:
                print(str(round(100*idx/length))+'%')
            found=0
            for shortidx,fish_i in enumerate(shortlist):
                if fish==fish_i:
                    occurencelist[shortidx].append(idx)
                    speciescomidlist[shortidx].append(comidlist[idx])
                    specieshuclist[shortidx].append(huclist[idx])
                    found=1
                    break
            if found==0:
                shortidx=len(shortlist)#-1 not needed since not yet appended
                shortlist.append(fish)
                specieshuclistidx.append([])
                occurencelist.append([idx])
                speciescomidlist.append([comidlist[idx]])
                specieshuclist.append([huclist[idx]])
                #print(f'new fish:{fish}')
            
            hucfound=0
            huc=huclist[idx]; 
            if not type(huc) is str:
                huc=str(huc)
            if len(huc)==7:
                huc='0'+huc
            assert len(huc)==8,print(f'expecting 8 characters: huc8_i:{huc}')
            
            
            for hucshortidx,huc_i in enumerate(shorthuclist):
                if huc==huc_i:
                    huccomidlist[hucshortidx].append(comidlist[idx])
                    specieshuclistidx[shortidx].append(huc)
                    hucfound==1
                    break
            if hucfound==0:
                shorthuclist.append(huc)
                huccomidlist.append([comidlist[idx]])
        print(f'buildspecieslist found {len(shortlist)} unique strings')
        
        with open(specieslistpath,'wb') as f:
            pickle.dump((shortlist,occurencelist,speciescomidlist,specieshuclist,shorthuclist,huccomidlist,specieshuclistidx),f)
        
        self.specieslist=shortlist
        self.speciesoccurencelist=occurencelist
        self.speciescomidlist=speciescomidlist
        self.specieshuclist=specieshuclist
        self.huclist=shorthuclist
        self.huccomidlist=huccomidlist
        self.specieshuclistidx=specieshuclistidx
            
    

            
            
    
    def buildCOMIDlist(self,):
        comidlistpath=os.path.join(self.savedir,'comidlist')
        if os.path.exists(comidlistpath):
            try:
                with open(comidlistpath,'rb') as f:
                    comidtup=pickle.load(f)
                self.comidlist=comidtup[0]
                self.comidcurrurencelist=comidtup[1]
                print(f'opening {comidlistpath} with length:{len(comidtup)} and has first item length: {len(self.comidlist)} and type:{type(self.comidlist)}')
                return
            except:
                print(f'error when opening {comidlistpath}')
            
        try: self.fishsurveydata
        except: self.getfishdata()
        print('building comidlist')
        longlist=[obs['COMID'] for obs in self.fishsurveydata]
        
        shortlist=[];occurencelist=[]
        length=len(longlist)
        i=0
        for idx,comid in enumerate(longlist):
            if idx%(length//33)==0:
                print(str(round(100*idx/length))+'%')
            found=0
            for shortidx,comid_i in enumerate(shortlist):
                if comid_i==comid:
                    occurencelist[shortidx].append(idx)
                    #print(f'old comid:{comid}')
                    found=1
                    break
            if found==0:
                shortlist.append(comid)
                occurencelist.append([idx])
        print(f'buildCOMIDlist found {len(shortlist)}')
        with open(comidlistpath,'wb') as f:
            pickle.dump((shortlist,occurencelist),f)
        
        self.comidlist=shortlist  
        self.comidoccurenclist=occurencelist
    
    def buildCOMIDsiteinfo(self,):
        filepath=os.path.join(self.savedir,'sitedatacomid_dict')
        if os.path.exists(filepath):
            try:
                with open(filepath,'rb') as f:
                    savefile=pickled.load(f)
                self.sitedatacomid_dict=savefile[0]
                self.comidsitedataidx=savefile[1]
                self.comidsiteinfofindfaillist=savefile[2]
                self.huc12findfaillist=savefile[3]
                print(f'opening {filepath} with length:{len(savefile)} and has first item length: {len(self.sitedatacomid_dict)} and type:{type(self.sitedatacomid_dict)}')
                return
            except:
                print(f'buildCOMIDsiteinfo found {filepath} but could not load it, so rebuilding')
        else:
            print(f'{filepath} does not exist, building COMID site info')   
        try: self.sitedata
        except:self.getsitedata()
        try:self.comidlist
        except:self.buildCOMIDlist()
        
        comidcount=len(self.comidlist)
        self.sitedata_k=len(self.sitedata[0])
        #self.sitevarkeylist=[key for key,_ in self.sitedata[0].items()]
        processcount=6
        '''self.comidsitedataidx=[]
        self.sitedatacomid_dict={}
        huc12findfaillist=[0]*comidcount
        huc12failcount=0
        comidsiteinfofindfaillist=[0]*comidcount
        self.huc12findfail=[]
        self.comidsiteinfofindfail=[]
        printselection=[int(idx) for idx in np.linspace(0,comidcount,101)]'''
        com_idx=[int(i) for i in np.linspace(0,comidcount,processcount+1)]#+1 to include the end
        print(com_idx)
        comidlistlist=[]
        for i in range(processcount):
            comidlistlist.append(self.comidlist[com_idx[i]:com_idx[i+1]])
        print('pool starting')
        with mp.Pool(processes=processcount) as pool:
            outlist=pool.map(self.mpsearchcomidhuc12,comidlistlist)
            sleep(2)
            pool.close()
            pool.join()
        print('pool complete')
        comidsitedataidx,sitedatacomid_dict,comidsiteinfofindfaillist,huc12findfaillist=zip(*outlist)
        self.comidsiteinfofindfaillist=[i for result in comidsiteinfofindfaillist for i in result]
        self.huc12findfaillist=[i for result in huc12findfaillist for i in result]
        self.sitedatacomid_dict=self.mergelistofdicts(sitedatacomid_dict)
        self.sitevarkeylist=[key for key in self.sitedatacomid_dict]
        
        self.comidsitedataidx=[]
        for i in range(processcount):
            self.comidsitedataidx.extend([j+com_idx[i] for j in comidsitedataidx[i]])
        
        
        with open(filepath,'wb') as f:
            pickle.dump((self.sitedatacomid_dict,self.comidsitedataidx,self.comidsiteinfofindfaillist,self.huc12findfaillist),f)
            
        self.comidsiteinfofindfail=[];self.huc12findfail=[]
        if sum(self.comidsiteinfofindfaillist)>0:
            for i in range(comidcount):
                if comidsiteinfofindfaillist[i]==1:
                    print(f'comidsiteinfofind failed for comid:{self.comidlist[i]}')
                    self.comidsiteinfofindfail.append(self.comidlist[i])
                
        if sum(self.huc12findfaillist)>0:
            for i in range(comidcount):
                if huc12findfaillist[i]==1:
                    print(f'huc12find failed for comid:{self.comidlist[i]}')
                    self.huc12findfail.append([self.comidlist[i]])

        return
 
    def mpsearchcomidhuc12(self,comidlist):
        mypid=os.getpid()
        comidcount=len(comidlist)
        comidsitedataidx=[]
        sitedatacomid_dict={}
        huc12findfaillist=[0]*comidcount
        huc12failcount=0
        comidsiteinfofindfaillist=[0]*comidcount
        
        printselection=[int(idx) for idx in np.linspace(0,comidcount,101)]
        for i,comid_i in enumerate(comidlist):
            if i in printselection and i>0:
                progress=np.round(100.0*i/comidcount,1)
                failrate=np.round(100.0*huc12failcount/i,5)
                print(f"{mypid}'s progress:{progress}%, failrate:{failrate}",end='. ')
            hucdatadict=self.findcomidhuc12reach(comid_i)
            if hucdatadict==None: 
                huc12findfaillist[i]=1
                huc12failcount+=1
            foundi=0
            
            for j,sitedict in enumerate(self.sitedata):
                comid_j=sitedict['COMID']
                if comid_i==comid_j:
                    foundi=1
                    comidsitedataidx.append(j)
                    if type(hucdatadict) is dict:
                        fullsitedict=self.mergelistofdicts([sitedict,hucdatadict])
                    else: 
                        if not hucdatadict==None:
                            print(f'{comid_i} hucdatadict is type:{type:hucdatadict} for i:{i},j:{j}')
                    sitedatacomid_dict[comid_j]=fullsitedict
                    break
            if foundi==0:
                comidsitedataidx.append(None)
                comidsiteinfofindfaillist[i]=1
        return (comidsitedataidx,sitedatacomid_dict,comidsiteinfofindfaillist,huc12findfaillist)
                
        

    def buildspecieshuc8list():
        try: self.fishhucs
        except: self.getfishhucs()
        specieshuc8list=[]*len(self.specieslist)
        lastid=None
        for item,i in enumerate(self.fishhucs):
            spec_i=item['Scientific_name']
            #d_i=item['ID']
            huc8_i=item['HUC']
            if not type(huc8_i) is str:
                huc8_i=str(huc8_i)
            if len(huc8_i)==7:
                huc8_i=0+huc8_i
            assert len(huc8_i)==8,print(f'expecting 8 characters: huc8_i:{huc8_i}')
            if not spec_i==lastspec_i:
                for j,spec_j in enumerate(self.specieslist):
                    if spec_i==spec_j:
                        specieslist_idx=j
            specieshuc8list[specieslist_idx].append(huc8_i)
            lastspec_i=spec_i    
        self.specieshuc8list=specieshuc8list
        
    def buildspecieshuccomidlist(self,):
        speciescount=len(self.specieslist)
        species01list=[]*speciescount
        specieshuc_allcomid=[]*speciescount
        for i,spec in enumerate(self.specieslist):
            foundincomidlist=self.speciescomidlist[i]
            hucidxlist=self.specieshuclistidx[i]
            for hucidx in hucidxlist:
                allhuccomids=self.huccomidlist[hucidx]
                specieshuc_allcomid[i].extend(allhuccomids)
                for comid in allhuccomids:
                    if comid in foundincomidlist:
                        species01list[i].extend(1)
                    else:
                        species01list[i].extend(0)
                
        self.specieshuc_allcomid=specieshuc_allcomid
        self.species01list=species01list
    
    def mergelistofdicts(self,listofdicts):
        mergedict={}
        for i,dict_i in enumerate(listofdicts):
            for key,val in dict_i.items():
                try:
                    mergedict[key]=val
                except KeyError:
                    newkey=key+f'_{i}'
                    print(f'for dict_{i} oldkey:{key},newkey:{newkey}')
                    mergedict[newkey]=val
        return
                    
    
    def findcomidhuc12reach(self,comid):
        try:self.NHDplus
        except:self.getNHDplus()
        itemcount=len(self.NHDplus)
        comid_digits=''.join(filter(str.isdigit,comid))
        datadict={}
        for i,NHDpluscomid in enumerate(self.NHDplus['COMID']):
            
            if str(NHDpluscomid)==comid_digits:
                #print(f'findcomidhuc12reach matched {comid} as {comid_digits}')
                for key in self.NHDvarlist:
                    datadict[key]=self.NHDplus[key][i]
                return datadict
            
        print(f'{comid_digits}',end=',')
        return None

    def buildspeciesdata01_file(self,):
        thisdir=self.savedir
        datadir=os.path.join(thisdir,'speciesdata01')
        if not os.path.exists(datadir):
            os.mkdir(datadir)
        try:self.specieslist
        except:self.buildspecieslist()
        try:self.comidlist
        except:self.buildCOMIDlist()
        try: self.sitedata
        except:self.getsitedata()
        try:self.sitedatacomid_dict,self.comidsitedataidx
        except: self.buildCOMIDsiteinfo()
        try: self.species01list,self.specieshuc_allcomid
        except: self.buildspecieshuccomidlist()
        
        
        for i,spec_i in enumerate(self.specieslist):
            try:
                species_filename=os.path.join(datadir,spec_i+'.data')
                if not os.path.exists(species_filename):
                    species_n=len(self.specieshuc_allcomid)
                    varcount=1+self.sitedata_k
                    speciesdata=np.empty(species_n,varcount)
                    speciesdata[:,0]=np.array(self.species01list).reshape(species_n,1)
                    for j,comid in enumerate(self.specieshuc_allcomid[i]):
                        sitevars=[self.sitedatacomid_dict[comid][key] for key in self.sitevarkeylist]
                        speciesdata[j,1:]=np.array(sitevars).reshape(1,self.sidedata_k)
                    with open(species_filename,'wb') as f:
                        pickle.dump(speciesdata,f)
                    with open(species_varname,'wb')as f:
                        pickle.dump(self.sitevarkeylist)
                else:
                    print(f'{species_filename} already exists')
            except:
                print(traceback.format_exc())
            

        return
            
        
        
    
    
if __name__=='__main__':
    test=DataTool()
    #test.getfishdata()
    #test.buildspecieslist()
    #test.buildCOMIDlist()
    test.buildCOMIDsiteinfo()
    test.buildspeciesdata01_file()
    
