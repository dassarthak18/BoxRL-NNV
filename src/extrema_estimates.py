import numpy as np
import csv
from pathlib import Path
from scipy.stats import qmc
from scipy.optimize import minimize

# We treat neural networks as a general MIMO black box
def black_box(sess, input_array, input_name, label_name, input_shape):
	reshaped_input_array = np.reshape(input_array, tuple(input_shape))
	try:
		value = sess.run([label_name], {input_name: reshaped_input_array.astype(np.float32)})[0][0]
		#if np.isnan(value).any():
		#	print(input_array)
		#	print(value)
		output_array = value.tolist()
	except TypeError:
		value = sess.run([label_name], {input_name: reshaped_input_array.astype(np.float32)})[0]
		#if np.isnan(value).any():
		#	print(input_array)
		#	print(value)
		output_array = value.tolist()
	return output_array

# We use Latin Hypercube Sampling to generate a near-random sample for preliminary extremum estimation
def extremum_best_guess(sess, lower_bounds, upper_bounds, input_name, label_name, input_shape, filename):
	# check no. of parameters, gracefully quit if necessary
	sampler = qmc.LatinHypercube(len(lower_bounds))
	inputsize = len(lower_bounds)
	if inputsize > 10**5:
		raise ValueError("Number of parameters too high, quitting gracefully.")
	else:
		n_samples = 15*inputsize
		lower_bounds = np.array(lower_bounds)
		upper_bounds = np.array(upper_bounds)
		n_total = len(lower_bounds)
		'''
  		non_const_indices = [i for i in range(n_total) if lower_bounds[i] < upper_bounds[i]]
		const_indices = [i for i in range(n_total) if lower_bounds[i] == upper_bounds[i]]
		if non_const_indices:
				sampler = qmc.LatinHypercube(d=len(non_const_indices))
				sample = sampler.random(n=n_samples)
				lb_sample = lower_bounds[non_const_indices]
				ub_sample = upper_bounds[non_const_indices]
				sample_scaled_pre = qmc.scale(sample, lb_sample, ub_sample)
		else:
				sample_scaled_pre = np.empty((n_samples, 0))
		sample_scaled = np.empty((n_samples, n_total))
		for i in range(n_samples):
				sample_i = np.empty(n_total)
				for idx in const_indices:
						sample_i[idx] = lower_bounds[idx]
				for j, idx in enumerate(non_const_indices):
						sample_i[idx] = sample_scaled[i, j]
				sample_scaled[i] = sample_i
    		'''
	sample = sampler.random(n_samples)
	sample_scaled = qmc.scale(sample, lower_bounds, upper_bounds)
	# compute the outputs
	sample_output = []
	for datapoint in sample_scaled:
		sample_output.append(black_box(sess, datapoint, input_name, label_name, input_shape))

	# cache the LHS inputs and outputs for future use
	LHSCacheFile = "../cache/" + filename[:-5] + "_lhs.csv"
	#LHSCacheFile.parent.mkdir(parents=True, exist_ok=True)
	with open(LHSCacheFile, mode='a', newline='') as cacheFile:
		writer = csv.writer(cacheFile, delimiter='|')
		if not Path(LHSCacheFile).exists():
        		writer.writerow(["input_lb", "input_ub", "input_array", "output_array"])
		writer.writerow([str(lower_bounds.tolist()), str(upper_bounds.tolist()), str(sample_scaled.tolist()), str(sample_output)])
	
	minima = [min(x) for x in zip(*sample_output)]
	maxima = [max(x) for x in zip(*sample_output)]
	# compute inputs for those guesses
	minima_inputs = []
	for i in range(len(minima)):
		for j in range(len(sample_output)):
			if sample_output[j][i] == minima[i]:
				minima_inputs.append(sample_scaled[j])
				break
	maxima_inputs = []
	for i in range(len(maxima)):
		for j in range(len(sample_output)):
			if sample_output[j][i] == maxima[i]:
				maxima_inputs.append(sample_scaled[j])
				break
	return [minima_inputs, maxima_inputs, minima, maxima]

# Objective function generator for L-BFGS-B
def create_objective_function(sess, input_shape, input_name, label_name, index, is_minima=True):
	def objective(x):
		arr = black_box(sess, x, input_name, label_name, input_shape)
		if is_minima:
			return arr[index]
		else:
			return -1*arr[index]
	return objective

# We use L-BFGS-B to refine our LHS extremum estimates
def extremum_refinement(sess, input_bounds, filename):
	# get neural network metadata
	input_name = sess.get_inputs()[0].name
	label_name = sess.get_outputs()[0].name
	# reshape if needed
	input_shape = [dim if isinstance(dim, int) else 1 for dim in sess.get_inputs()[0].shape]
	# get the lower and upper input bounds
	lower_bounds = input_bounds[0]
	upper_bounds = input_bounds[1]
	# get the preliminary estimates
	try:
		extremum_guess = extremum_best_guess(sess, lower_bounds, upper_bounds, input_name, label_name, input_shape, filename)
		bounds = list(zip(lower_bounds, upper_bounds))
		# refine the minima estimate
		minima_inputs = extremum_guess[0]
		minima = extremum_guess[2]
		updated_minima = []
		updated_minima_inputs = []
		for index in range(len(minima)):
			objective = create_objective_function(sess, input_shape, input_name, label_name, index)
			x0 = list(minima_inputs[index])
			result = minimize(objective, method = 'L-BFGS-B', bounds = bounds, x0 = x0, options = {'disp': False, 'gtol': 1e-4, 'maxiter': 100, 'eps': 1e-12})
			if result.fun > minima[index]:
				updated_minima_inputs.append(x0)
				updated_minima.append(minima[index])
			else:
				updated_minima_inputs.append(result.x.tolist())
				updated_minima.append(result.fun)
		# refine the maxima estimate
		maxima_inputs = extremum_guess[1]
		maxima = extremum_guess[3]
		updated_maxima = []
		updated_maxima_inputs = []
		results_maxima = []
		for index in range(len(maxima)):
			objective = create_objective_function(sess, input_shape, input_name, label_name, index, is_minima=False)
			x0 = list(maxima_inputs[index])
			result = minimize(objective, method = 'L-BFGS-B', bounds = bounds, x0 = x0, options = {'disp': False, 'gtol': 1e-4, 'maxiter': 100, 'eps': 1e-12})
			if -result.fun < maxima[index]:
				updated_maxima_inputs.append(x0)
				updated_maxima.append(maxima[index])
			else:
				updated_maxima_inputs.append(result.x.tolist())
				updated_maxima.append(-result.fun)
		# cache the computer bounds for future use
		boundsCacheFile = "../cache/" + filename[:-5] + "_bounds.csv"
		#boundsCacheFile.parent.mkdir(parents=True, exist_ok=True)
		with open(boundsCacheFile, mode='a', newline='') as cacheFile:
			writer = csv.writer(cacheFile, delimiter='|')
			if not Path(boundsCacheFile).exists():
	        		writer.writerow(["input_lb", "input_ub", "output_lb", "output_ub", "minima_inputs", "maxima_inputs"])
			writer.writerow([str(lower_bounds), str(upper_bounds), str(updated_minima), str(updated_maxima), str(updated_minima_inputs), str(updated_maxima_inputs)])
			
		return [updated_minima_inputs, updated_maxima_inputs, updated_minima, updated_maxima]
	except ValueError:
		raise ValueError("Number of parameters too high, quitting gracefully.")
