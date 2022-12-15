# heater_plugin

import pcbnew

def pcbpoint(p):
    return pcbnew.wxPointMM(float(p[0]), float(p[1]))

def vectorAdd(a,b):
	return [a[0]+b[0], a[1]+b[1]]

class heaterPlugin(pcbnew.ActionPlugin):
	"""draw a heater trace based on
	a prescribed pattern"""
	def defaults(self):
		self.name        = "Heater Plugin"
		self.category    = "Modify PCB"
		self.description = "Draws a pattern of tracks for a heater"
		self.show_toolbar_button = True

		#yea I did it- I hardcoded the constants
		self.w = .996
		self.h = .267
		self.n = 38
		self.L = 84
		self.H = 98


	def drawStraight(self,x1,y1,x2,y2,board,group):
		track = pcbnew.PCB_TRACK(board)
		track.SetStart(pcbpoint((x1,y1)))
		track.SetEnd(pcbpoint((x2,y2)))
		track.SetWidth(int(self.w*1e6))
		track.SetLayer(pcbnew.F_Cu)
		board.Add(track)
		group.AddItem(track)

	def Run(self):
		board = pcbnew.GetBoard()
		group = pcbnew.PCB_GROUP(board)
		board.Add(group)

		vectorList = [[0,(self.h+self.w)],[(self.L-self.h-self.w)/2, 0],[0,(self.h+self.w)],[-1*(self.L-self.h-self.w)/2, 0]]
		vectorListB = [[0,-1*(self.h+self.w)],[-1*(self.L-self.h-self.w)/2, 0],[0,-1*(self.h+self.w)],[(self.L-self.h-self.w)/2, 0]]

		#generate endpoint list starting at 0,0, or another seed point
		orderedPoints = []
		orderedPoints.append([0,0])

		#draw first side
		for row in range(self.n*4):
			# generate points
			nextPoint = vectorAdd(orderedPoints[-1], vectorList[row%4])
			orderedPoints.append(nextPoint)

		#add one more "down" point
		nextPoint = vectorAdd(orderedPoints[-1], vectorList[0])
		orderedPoints.append(nextPoint)

		#traverse "across" a whole L
		nextPoint = vectorAdd(orderedPoints[-1], (self.L,0))
		orderedPoints.append(nextPoint)

		#draw second side
		for row in range(self.n*4):
			# generate points
			nextPoint = vectorAdd(orderedPoints[-1], vectorListB[row%4])
			orderedPoints.append(nextPoint)

		#add one more "up" point
		nextPoint = vectorAdd(orderedPoints[-1], vectorListB[0])
		orderedPoints.append(nextPoint)

		#traverse "across" a whole L
		nextPoint = vectorAdd(orderedPoints[-1], (-self.L,0))
		orderedPoints.append(nextPoint)
		
		for index in range(len(orderedPoints)-1):
			x1=orderedPoints[index][0]
			y1=orderedPoints[index][1]
			x2=orderedPoints[index+1][0]
			y2=orderedPoints[index+1][1]

			self.drawStraight(x1,y1,x2,y2,board,group)





heaterPlugin().register()