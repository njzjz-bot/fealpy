import sys
import numpy as np

def show_error_table(N, errorType, errorMatrix, pre=5, sep=' & ', out=sys.stdout, end='\n'):

    flag = False
    if type(out) == type(''):
        flag = True
        out = open(out, 'w')

    n = errorMatrix.shape[1] + 1
    print('\\begin{table}[!htdp]', file=out, end='\n')
    print('\\begin{tabular}[c]{|'+ n*'c|' + '}\\\\\hline', file=out, end='\n')

    s = 'Dof' + sep + np.array2string(N, separator=sep,
            )
    s = s.replace('\n', '')
    s = s.replace('[', '')
    s = s.replace(']', '')
    print(s, file=out, end=end)

    n = len(errorType)
    for i in range(n):
        first = errorType[i]
        line = errorMatrix[i]
        s = first + sep + np.array2string(line, separator=sep,
                precision=pre)
        s = s.replace('\n', '')
        s = s.replace('[', '')
        s = s.replace(']', '')
        print(s, file=out, end=end)

        order = np.log(line[0:-1]/line[1:])/np.log(2)
        s = 'Order' + sep + '--' + sep + np.array2string(order,
                separator=sep, precision=2)
        s = s.replace('\n', '')
        s = s.replace('[', '')
        s = s.replace(']', '')
        print(s, file=out, end=end)

    print('\\end{tabular}', file=out, end='\n')
    print('\\end{table}', file=out, end='\n')

    if flag:
        out.close()

def showrate(axes, k, N, error, option, label=None):
    line0, = axes.loglog(N, error, option, lw=2, label=label)
    c = np.polyfit(np.log(N[k:]), np.log(error[k:]), 1)
    s = 0.75*error[k]/N[k]**c[0] 
    line1, = axes.loglog(N[k:], s*N[k:]**c[0], label='C$N^{%0.4f}$'%(c[0]))
    axes.legend()
