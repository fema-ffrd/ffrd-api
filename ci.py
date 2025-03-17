import scipy.stats as st
import math
def confidence_interval_values(haz_stats:dict,realizations:int = 5,distribution:str = 'normal',confidence_level:float = .9):
    """
    Description:
        Converts post-processed information about hazards (mean, standard deviation, number to determine the associated confidence interval values.
    Inputs:
        haz_stats: dict - must include the keys 'mean' and 'std_dev' with associated values in the dictionary (e.g., {'mean':22.405237,'std_dev':0.940294})
        realizations: int - number of realizations of the study. assumed to be 5 unless the user provides more information.
        distribution: str - Z score is based on normal distribution but could be updated in the function if that is not appropriate.
    Returns:
        A dictionary with the name of the confidence intervals as keys and the values based on the statistical function:
             lower limit = x̄ - z* * SE 
             upper limit is x̄ + z* * SE
             where SE is the standard error calculated by the equation  σ / √n
            
            key:
                σ: standard deviation
                x̄: mean
                n: number of samples (realizations)
                z*: Z score

    """
    #calculate z scores
    alpha = 1 - confidence_level
    p = alpha/2
    if distribution=='normal':
        z_lower = st.norm.ppf(p)
        z_upper = st.norm.ppf(1 - p)
    else:
        print('only normal distribution is currently implemented')
        return None

    #error
    std_error_low = z_lower*(haz_stats['std_dev']/math.sqrt(realizations))
    std_error_up = z_upper*(haz_stats['std_dev']/math.sqrt(realizations))
    lbound = '{:.2f}'.format(round(p,2))
    ubound = '{:.2f}'.format(round(1-p,2))
    result =  {f'lower_val':haz_stats['mean']+std_error_low,f'upper_val':haz_stats['mean']+std_error_up,f'lower_bound':lbound,f'upper_bound':ubound}
    return result