import numpy as np
import util

class AudioWatermarkingMCLT():
	pass

	def __init__(self):
		pass

	@staticmethod
	def singleChannelEmbed(au, awmOpt):
		# set variables
		M = int(awmOpt.frameSize / 2)
		C = AudioWatermarkingMCLT.co(M)
		S = AudioWatermarkingMCLT.si(M)
		W = AudioWatermarkingMCLT.Wa(M)
		C1 = C[:, 0:M]
		C2 = C[:, M:2*M]
		S1 = S[:, 0:M]
		S2 = S[:, M:2*M]
		W1 = W[0:M, 0:M]
		W2 = W[M:2*M, M:2*M]
		A_1 = C1 * W1 * W2 * S2.transpose()
		A1 = C2 * W2 * W1 * S1.transpose()
		B_1 = S1 * W1 * W2 * C2.transpose()
		B1 = S2 * W2 * W1 * C1.transpose()
		sync = awmOpt.syncSeq.reshape(-1, int((awmOpt.syncFreqBand[1]-awmOpt.syncFreqBand[0])/2+1)).T
		dataSeq = AudioWatermarkingMCLT.string2binary(awmOpt.data)
		bitPerFrame = int((awmOpt.dataFreqBand[1]-awmOpt.dataFreqBand[0]+1) / awmOpt.spreadLen)
		syncFrameSize = int(np.size(sync) / ((awmOpt.syncFreqBand[1]-awmOpt.syncFreqBand[0])/2+1)*2)
		dataFrameSize =  int(np.ceil(np.size(dataSeq)/bitPerFrame))
		blockSize = syncFrameSize + dataFrameSize
		frameMat = util.enframe(au, awmOpt.frameSize, awmOpt.overlap)
		# data matrix
		if (np.size(dataSeq) % bitPerFrame) != 0:
			zeroToBePadded = np.zeros((1, dataFrameSize*bitPerFrame-np.size(dataSeq)), dtype=int)
			remainPart = np.size(zeroToBePadded)
			dataSeq = np.concatenate((dataSqe, zeroToBePadded), 1)
		data = np.kron(np.ones((awmOpt.spreadLen, 1)), dataSeq).T.reshape(-1, awmOpt.dataFreqBand[1]-awmOpt.dataFreqBand[0]+1).T

		# fast MCLT
		#fmcltk = np.array(range(0, M+1), dtype=np.float64)
		#fmcltc = AudioWatermarkingMCLT.compExpo(8, 2*fmcltk+1) * AudioWatermarkingMCLT.compExpo(4*M, fmcltk)
		X = AudioWatermarkingMCLT.fmclt2(frameMat)

		# data Embed
		xBar = X
		Xc = X.real
		Xs = -X.imag
		for b in range(0, int(np.floor(X.shape[1]/blockSize))*blockSize, blockSize):
			# synchronization
			# i is for frame index
			# k is for frequency index
			i = np.arange(b+1, b+syncFrameSize, 2)
			k = np.arange(awmOpt.syncFreqBand[0], awmOpt.syncFreqBand[1]+1, 2)
			xBarCSub = A_1[np.ix_(k, range(0, A_1.shape[1]))]*Xs[np.ix_(range(Xs.shape[0]), i-1)] + 0.5*Xs[np.ix_(k-1, i)] - 0.5*Xs[np.ix_(k+1, i)] + A1[np.ix_(k, range(0, A1.shape[1]))]*Xs[np.ix_(range(0, Xs.shape[0]), i+1)]
			xBarC = np.multiply(np.absolute(X[np.ix_(k, i)]), sync) - xBarCSub
			xBarS = -(B_1[np.ix_(k, range(0, B_1.shape[1]))]*Xc[np.ix_(range(0, Xc.shape[0]), i-1)] - 0.5*Xc[np.ix_(k-1, i)] + 0.5*Xc[np.ix_(k+1, i)] + B1[np.ix_(k, range(0, B1.shape[1]))]*Xc[np.ix_(range(0, Xc.shape[0]), i+1)])
			xBar[np.ix_(k, i)] = xBarC - 1j * xBarS

			# data
			# p is for frame index
			# q is for frequency index
			p = np.arange(b+syncFrameSize, b+syncFrameSize+dataFrameSize)
			q = np.arange(awmOpt.dataFreqBand[0], awmOpt.dataFreqBand[1]+1)
			xBar[np.ix_(q, p)] = np.multiply(np.absolute(X[np.ix_(q, p)]), data)
			# copy original value
			if (np.size(dataSeq) % bitPerFrame) != 0:
				xBar[np.ix_(q[awmOpt.dataFreqBand[1]-remainPart+1:awmOpt.dataFreqBand[1]], p[-1])] = X[np.ix_(q[awmOpt.dataFreqBand[1]-remainPart+1:awmOpt.dataFreqBand[1]], p[-1])]

		# fast inverse MCLT
		output = AudioWatermarkingMCLT.fimclt2(xBar, awmOpt)
		return output

	#def awmExtract(self):

	@staticmethod
	def extractMCLT(y, index, awmOpt):
		dataSeq = AudioWatermarkingMCLT.string2binary(awmOpt.data)
		bitPerFrame = int((awmOpt.dataFreqBand[1]-awmOpt.dataFreqBand[0]+1) / awmOpt.spreadLen)
		syncFrameSize = int(np.size(awmOpt.syncSeq) / ((awmOpt.syncFreqBand[1]-awmOpt.syncFreqBand[0])/2+1)*2)
		dataFrameSize =  int(np.ceil(np.size(dataSeq)/bitPerFrame))
		blockSize = syncFrameSize + dataFrameSize
		tmp = util.enframe(y[index:index+(blockSize-1)*(awmOpt.frameSize-awmOpt.overlap)+awmOpt.frameSize], awmOpt.frameSize, awmOpt.overlap)
		block = AudioWatermarkingMCLT.fmclt2(tmp)
		cipher = np.matrix(np.zeros((1, bitPerFrame*dataFrameSize), dtype=np.int))
		count = 0
		rowIndex = np.arange(awmOpt.dataFreqBand[0], awmOpt.dataFreqBand[1]+1, awmOpt.spreadLen)
		for i in range(syncFrameSize, block.shape[1]):
			for j in range(bitPerFrame):
				positive = len(np.nonzero(np.sign(block[rowIndex[j]:rowIndex[j]+awmOpt.spreadLen, i].real) == 1)[0])
				negative = len(np.nonzero(np.sign(block[rowIndex[j]:rowIndex[j]+awmOpt.spreadLen, i].real) == -1)[0])
				if positive >= negative:
					cipher[0, count] = 1
				else:
					cipher[0, count] = -1
				count = count + 1
		if (dataSeq.shape[1] % bitPerFrame) != 0:
			cipher = cipher[0, 0:dataSeq.shape[1]]
		return cipher

	@staticmethod
	def findSyncFast(y, base, length, awmOpt):
		M = int(awmOpt.frameSize/2)
		cor = np.matrix(np.zeros((length, 1), dtype=np.complex_))
		sync = awmOpt.syncSeq.reshape(-1, int((awmOpt.syncFreqBand[1]-awmOpt.syncFreqBand[0])/2+1)).T
		syncFrameSize = int(np.size(sync) / ((awmOpt.syncFreqBand[1]-awmOpt.syncFreqBand[0])/2+1)*2)
		j = np.arange(1, syncFrameSize, 2)
		k = np.arange(awmOpt.syncFreqBand[0], awmOpt.syncFreqBand[1]+1, 2)

		fmcltk = np.matrix(range(0, M+1), dtype=np.float64).reshape(-1, 1)
		fmcltc = np.multiply(AudioWatermarkingMCLT.compExpo(8, 2*fmcltk+1), AudioWatermarkingMCLT.compExpo(4*M, fmcltk))
		for i in range(base, base+length):
			truncated = util.enframe(y[i:i+(syncFrameSize-1)*512+1024], awmOpt.frameSize, awmOpt.overlap)
			embed = AudioWatermarkingMCLT.fmclt3(truncated, fmcltc)
			cor[i-base, 0] = np.sum(np.divide(np.multiply(embed[np.ix_(k, j)], sync), np.absolute(embed[np.ix_(k, j)])))
		return cor

	@staticmethod
	def compExpo(M, r):
		return np.exp(-1j*2*np.pi*r/M)

	@staticmethod
	def fmclt(x):
		# MCLT of a single vector
		M =int(len(x)/2)
		U = np.matrix(np.sqrt(1/(2*M)) * np.fft.fft(x.T)).T
		k = np.matrix(range(0, M+1), dtype=np.float64).reshape(-1, 1)
		c = np.multiply(AudioWatermarkingMCLT.compExpo(8, 2*k+1), AudioWatermarkingMCLT.compExpo(4*M, k))
		V = np.multiply(c, U[0:M+1])
		X = 1j * V[0:M] + V[1:M+1]
		return X

	# if you need to call fmclt just one time, use this
	@staticmethod
	def fmclt2(frameMat):
		M = int(frameMat.shape[0]/2)
		k = np.matrix(range(0, M+1), dtype=np.float64).reshape(-1, 1)
		c = np.multiply(AudioWatermarkingMCLT.compExpo(8, 2*k+1), AudioWatermarkingMCLT.compExpo(4*M, k))
		X = np.matrix(np.zeros((M, frameMat.shape[1]), dtype=np.complex_))
		for i in range(frameMat.shape[1]):
			U = np.matrix(np.sqrt(1/(2*M)) * np.fft.fft(frameMat[:, i].T)).T
			V = np.multiply(c, U[0:M+1])
			X[:, i] = 1j * V[0:M] + V[1:M+1]
		return X

	# if you need to call fmclt function many times, use this
	@staticmethod
	def fmclt3(frameMat, c):
		# MCLT of a frame matrix
		M = int(frameMat.shape[0]/2)
		X = np.matrix(np.zeros((M, frameMat.shape[1]), dtype=np.complex_))
		for i in range(frameMat.shape[1]):
			U = np.matrix(np.sqrt(1/(2*M)) * np.fft.fft(frameMat[:, i].T)).T
			V = np.multiply(c, U[0:M+1])
			X[:, i] = 1j * V[0:M] + V[1:M+1]
		return X

	@staticmethod
	def fimclt(X):
		M = len(X)
		Y = np.matrix(np.zeros((2*M, 1), dtype=np.complex_))
		k = np.matrix(range(1, M), dtype=np.float64).reshape(-1, 1)
		c = np.multiply(AudioWatermarkingMCLT.compExpo(8, 2*k+1), AudioWatermarkingMCLT.compExpo(4*M, k))
		Y[1:M] = (1/4) * np.multiply(np.conj(c), (X[0:M-1] - 1j * X[1:M]))
		Y[0] = np.sqrt(1/8) * (X[0].real + X[0].imag)
		Y[M] = -np.sqrt(1/8) * (X[M-1].real + X[M-1].imag)
		Y[M+1:2*M] = np.conj(Y[range(M-1, 0, -1)])
		yBar = np.matrix(np.fft.ifft(np.sqrt(2*M) * Y.T).real).T
		return yBar

	@staticmethod
	def fimclt2(X, awmOpt):
		M = X.shape[0]
		Y = np.matrix(np.zeros((2*M, 1), dtype=np.complex_))
		yBar = np.matrix(np.zeros((2*M, X.shape[1]), dtype=np.float64))
		k = np.matrix(range(1, M), dtype=np.float64).reshape(-1, 1)
		c = np.multiply(AudioWatermarkingMCLT.compExpo(8, 2*k+1), AudioWatermarkingMCLT.compExpo(4*M, k))
		# fast inverse mclt
		for i in range(0, X.shape[1]):
			Y[1:M] = (1/4) * np.multiply(np.conj(c), (X[0:M-1, i] - 1j * X[1:M, i]))
			Y[0] = np.sqrt(1/8) * (X[0, i].real + X[0, i].imag)
			Y[M] = -np.sqrt(1/8) * (X[M-1, i].real + X[M-1, i].imag)
			Y[M+1:2*M] = np.conj(Y[range(M-1, 0, -1)])
			yBar[:, i] = np.matrix(np.fft.ifft(np.sqrt(2*M) * Y.T).real).T
		
		# overlap add
		output = np.matrix(np.zeros((awmOpt.frameSize, yBar.shape[1]), dtype=np.float64))
		for i in range(1, yBar.shape[1]-1):
			output[:, i] = np.vstack((yBar[awmOpt.frameSize/2:, i-1], yBar[0:awmOpt.frameSize/2, i+1])) + yBar[:, i]
		# deal with first and last frame
		output[:, 0] = output[:, 0] + np.vstack((np.zeros((int(awmOpt.frameSize/2), 1), dtype=np.float64), output[0:int(awmOpt.frameSize/2), 1]))
		output[:, -1] = output[:, -1] + np.vstack((output[awmOpt.frameSize/2:, -2], np.zeros((int(awmOpt.frameSize/2), 1), dtype=np.float64)))
		output2 = np.vstack((output[:, 0], (output[awmOpt.frameSize/2:, 1:].T.reshape(-1, 1))))
		return output2


	@staticmethod
	def string2binary(message):
		asc = [bin(ord(i))[2:].zfill(8) for i in message]
		code = np.matrix(list(''.join(asc)), dtype=int)
		pos = (code==0).nonzero()
		code[pos] = -1
		return code

	@staticmethod
	def cipher2plain(cipher):
		pos = (cipher == -1).nonzero()
		cipher[pos] = 0
		byte = [str(cipher[0, i]) for i in range(0, max(cipher.shape))]
		byte = ''.join(byte)
		plain = [chr(int(byte[i:i+8], 2)) for i in range(0, len(byte), 8)]
		plain = ''.join(plain)
		return plain

	@staticmethod
	def co(M):
		C = np.matrix([[np.sqrt(2/M)*np.cos((j+((M+1)/2))*(i+0.5)*np.pi/M) for j in range(0, 2*M)] for i in range(0, M)], dtype=np.float64)
		return C

	@staticmethod
	def si(M):
		S = np.matrix([[np.sqrt(2/M)*np.sin((j+((M+1)/2))*(i+0.5)*np.pi/M) for j in range(0, 2*M)] for i in range(0, M)], dtype=np.float64)
		return S

	@staticmethod
	def Wa(M):
		W = np.matrix(np.diag(np.array([-np.sin((i+0.5)*np.pi/(2*M)) for i in range(0, 2*M)], dtype=np.float64)))
		return W

def main():
	from awmOptSet import AwmOptSet as awmOptSet
	import scipy.io
	import time
	#import util
	fs, au = util.audioread('./testAudio/mono.wav')
	awmOpt = awmOptSet('mclt')
	output = AudioWatermarkingMCLT.singleChannelEmbed(au, awmOpt)
	startTime = time.time()
	cor = AudioWatermarkingMCLT.findSyncFast(output, 0, 100, awmOpt)
	print('Elapsed time: %s\n', (time.time() - startTime))
	pos = np.nonzero(cor.real > 100)
	ci = AudioWatermarkingMCLT.extractMCLT(output, pos[0][0], awmOpt)
	plain = AudioWatermarkingMCLT.cipher2plain(ci)
	print(plain)

if __name__ == '__main__':
	main()