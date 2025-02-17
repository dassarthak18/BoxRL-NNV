from extrema_estimates import black_box
from z3 import *

def spuriousCE_check(solver, sess):
  input_name = sess.get_inputs()[0].name
  label_name = sess.get_outputs()[0].name
  input_shape = [dim if isinstance(dim, int) else 1 for dim in sess.get_inputs()[0].shape]

  while str(solver.check()) == "sat":
    model = solver.model()
    input_vars = []
    output_vars = []
    input_vals = []
    output_vals = []
    for i in model:
      if "X" in str(i):
        input_vars.append(str(i))
      else:
        output_vars.append(str(i))
    input_vars = sorted(input_vars)
    output_vars = sorted(output_vars)
    for i in range(len(input_vars)):
      x = Real(input_vars[i])
      input_vals[i] = float(model.eval(x).as_decimal(20))
    for j in range(len(output_vars)):
      y = Real(output_vars[j])
      output_vals[j] = float(model.eval(y).as_decimal(20))
    output_vals_true = black_box(sess, input_vals, input_name, label_name, input_shape)
    
    if np.allclose(output_vals, output_vals_true, atol=1e-15):
      return "violated " + f"\n{str(model)}"
    else:
      variables = [Real(x) for x in input_vars+output_vars]
      solver.add(Or([v != model[v] for v in variables]))
  return "unknown"
