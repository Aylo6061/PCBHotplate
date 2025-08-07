from math import sqrt, floor, ceil
import matplotlib.pyplot as plt


TargetResistance = 6.5 #desired heater resistance
OhmsPerSquare = .0005 #ohms per square for 1 oz copper

PatternHeight = 97 #mm, subtract off any margin you want to board edge
PatternLength = 97

S = TargetResistance/OhmsPerSquare #target number of squares

wpos = []
wneg = []
Nlist = []
Haxis =[] #a list for the horizontal axis of the final list.  represents track spacing

stepsize = .001 #step size, mm
min_h=.16 #minimun trace height, mm
max_h=.4  #maximum trace height, mm

#figure out how many steps to try between min/max h
steps = floor((max_h-min_h)/stepsize)

#iterate through solutions for a given h
for delta in range(0, steps):
	#calculate a height, min size+stepsize*iteration
	h= .16+delta*stepsize

	#append h for later display
	Haxis.append(h) 

	#solve for what the pattern would be at this step size

	a = S
	b = (h*S)+(2*h)
	c = -1*((h*PatternHeight)+(2*h*PatternLength)+(PatternHeight*PatternLength))

	try:
		pos_root=(-b+sqrt(b**2-4*a*c))/(2*a)
	except ValueError:
		pass #its possible that there is no real positive root
	wpos.append(pos_root) #append the positive width 

	N = (PatternHeight-2*pos_root)/(2*pos_root+2*h) #number of pattern repeats
	Htot = 2*pos_root + N * (2*pos_root+2*h) #total height
	# print(f"N: {N}, Htot: {Htot}")
	try:
		wneg.append((-b-sqrt(b**2-4*a*c))/(2*a))
	except ValueError:
		pass
	Nlist.append(N) #append negative root


Hpruned = []
Npruned = []
Wpruned = []

#prune the list so that only very nearly integer results for N repetitions are reported
for x, y, z in zip(Haxis, Nlist, wpos):
	if(y%1<.01):
		Hpruned.append(x)
		Npruned.append(y)
		Wpruned.append(z)

fig, ax1 = plt.subplots()
ax2 = ax1.twinx()

ax1.plot(Haxis,wpos, color = 'k')
ax2.scatter(Hpruned,Npruned, color = 'r')
ax2.set_ylim(min(Nlist)-.15,max(Nlist)+.15)
ax2.set_xlim(min(Haxis),max(Haxis))
plt.suptitle("Track width and Pattern Count")
ax1.set_xlabel("Track spacing, mm")
ax1.set_ylabel("track width, mm")
ax2.set_ylabel("Pattern count")
plt.show()

for x,y,z in zip(Hpruned,Npruned,Wpruned):
	print(f"w width {z}, h spacing {x}, N repeats {y}")

