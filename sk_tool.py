from sklearn.pipeline import make_pipeline
from sklearn.linear_model import ElasticNetCV, LinearRegression
from sklearn.svm import LinearSVR, SVR
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_validate, train_test_split, RepeatedKFold, GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, f1_score, average_precision_score
from sklearn.ensemble import GradientBoostingRegressor

class skTool()
    def __init__(self,xtrain,xtest,ytrain,ytest):
        linear_regression=make_pipeline(StandardScaler(),LinearRegression())
        elastic_net = make_pipeline(StandardScaler(), ElasticNetCV())
        #linear_svr = make_pipeline(StandardScaler(),GridSearchCV(LinearSVR(random_state=rs,tol=1e-3,max_iter=5000),n_jobs=1,param_grid={'C':np.linspace(-1,4,8)}))
        linear_svr = make_pipeline(StandardScaler(),LinearSVR(random_state=rs,tol=1e-4,max_iter=5000,C=1))
        rbf_svr=make_pipeline(StandardScaler(),SVR(kernel='rbf',tol=1e-4,max_iter=5000, C=1))
        gradient_boosting_reg=make_pipeline(StandardScaler(),GradientBoostingRegressor())
        model_dict={'linear-regression':linear_regression,
            'elastic-net':elastic_net, 
            'linear-svr':linear_svr, 
            'rbf-svr':rbf_svr, 
            'gradient-boosting-reg':gradient_boosting_reg}
        loss_fn_dict={'mse':mean_squared_error, 'mae':mean_absolute_error, 'r2':r2_score, 'f1_score':f1_score, 'average_precision_score':average_precision_score}
        yhatdict={}
        for model_name,model in model_dict.items():
            model.fit(xtrain,ytrain)
            ytesthat=model.predict(xtest)
            resultdict[model_name]=ytesthat
            #yhatdict[model_name]={lf_name:lf(ytest,ytesthat) for lf_name,lf in loss_fn_dict.items()}
        return yhatdict
            
        
            