#Ryan A. Melnyk
#schmelnyk@gmail.com
#UBC Microbiology - Haney Lab

import os, argparse, subprocess, errno, sys, string
import multiprocessing as mp
import pyparanoid.pyparanoid as pp
from Bio import SeqIO

def parse_args():
	parser = argparse.ArgumentParser(description='''
Takes a complete PyParanoid directory (base and propagated) and generate list of orthologs. Using the 'threshold'
argument relaxes the cutoff and includes homologs that occur exactly once in some fraction of all strains (e.g. 90%).
	''')
	parser.add_argument('outdir', type=str,help='path to PyParanoid folder')
	parser.add_argument('prefix',type=str,help='prefix for output files')
	parser.add_argument('--threshold',type=float,help='proportion of strains to be considered an ortholog')
	parser.add_argument('--cpus',type=int,help='number of CPUs to use for tasks. Defaults to # of cores available.')
	parser.add_argument('--clean',action="store_true",help="clean up intermediate files")
	parser.add_argument('--strains',type=str,help='specify if a subset of strains are to be identified')
	parser.add_argument('--orthos',type=str,help="specify to use previously calculated groups")
	return parser.parse_args()


def parse_matrix(strains):
	orthos = []
	print "Parsing matrix to identify orthologs..."
	header = open(os.path.join(outdir,"homolog_matrix.txt")).readline().rstrip().split("\t")
	try:
		indices = [header.index(s) for s in strains]
	except:
		print s,"not found in matrix. Check strainlist."
	for line in open(os.path.join(outdir,"homolog_matrix.txt")):
		vals = line.rstrip().split("\t")
		if vals[0] == "":
			continue
		else:
			strain_vals = [vals[i] for i in indices]
			if set(strain_vals[1:]) == set(["1"]):
				orthos.append(vals[0])
	print len(orthos), "orthologs found."
	return orthos

def parse_threshold_matrix(t,strains):
	orthos = []
	print "Parsing matrix to identify orthologs..."
	header = open(os.path.join(outdir,"homolog_matrix.txt")).readline().rstrip().split("\t")
	try:
		indices = [header.index(s) for s in strains]
	except:
		print s,"not found in matrix. Check strainlist."
	for line in open(os.path.join(outdir,"homolog_matrix.txt")):
		vals = line.rstrip().split("\t")
		if vals[0] == "":
			continue
		else:
			strain_vals = [vals[i] for i in indices]
			if float(strain_vals.count("1"))/float(len(strain_vals)) > t:
				orthos.append(vals[0])
	print len(orthos), "orthologs found."
	return orthos

def concat_orthos(orthos,strains,cpus):
	count = len(orthos)
	print "Concatenating {} ortholog files...".format(str(count))
	pool = mp.Pool(processes=cpus)
	[pool.apply_async(concat, args=(o,strains)) for o in orthos]
	pool.close()
	pool.join()
	return

def concat(o,strains):
	selected = []
	out = open(os.path.join(outdir,"concat",o+".faa"),'w')
	try:
		for seq in SeqIO.parse(open(os.path.join(outdir,"homolog_faa",o+".faa"),'r'),'fasta'):
			strain = str(seq.id).split("|")[0]
			if strain in strains:
				if strain not in selected:
					out.write(">{}\n{}\n".format(strain,str(seq.seq)))
					selected.append(strain)
	except IOError:
		pass
	try:
		for seq in SeqIO.parse(open(os.path.join(outdir,"prop_homolog_faa",o+".faa"),'r'),'fasta'):
			strain = str(seq.id).split("|")[0]
			if strain in strains:
				if strain not in selected:
					out.write(">{}\n{}\n".format(strain,str(seq.seq)))
					selected.append(strain)
	except IOError:
		pass
	out.close()
	return

def align_orthos(orthos,cpus):
	count = len(orthos)
	print "Aligning {} ortholog files...".format(str(count))
	pool = mp.Pool(processes=cpus)
	[pool.apply_async(hmmalign, args=(o,)) for o in orthos]
	pool.close()
	pool.join()
	return

def hmmalign(o):
	cmds = "hmmalign -o {} {} {}".format(os.path.join(outdir,"ortho_align",o+".sto"),os.path.join(outdir,"hmms",o+".hmm"),os.path.join(outdir,"concat",o+".faa"))
	proc = subprocess.Popen(cmds.split())
	proc.wait()
	return

def extract_hmms(orthos):
	count = len(orthos)
	present = [f.split(".")[0] for f in os.listdir(os.path.join(outdir,"hmms"))]
	print "Extracting {} HMM files...{} already found.".format(str(count),str(len(present)))
	FNULL = open(os.devnull, 'w')
	for o in orthos:
		count -= 1
		if o in present:
			pass
		else:
			cmds = "hmmfetch -o {} {} {}".format(os.path.join(outdir,"hmms",o+".hmm"),os.path.join(outdir,"all_groups.hmm"),o)
			proc = subprocess.Popen(cmds.split(),stdout=FNULL,stderr=FNULL)
			proc.wait()
		if count % 100 == 0:
			print "\t"+str(count), "remaining..."
		else:
			pass
	if count == 0:
		print "\tDone!"
	FNULL.close()
	return

def create_master_alignment(orthos,strains,prefix):

	align_data = {k : [] for k in strains}
	count = len(orthos)
	total_leng = 0 ###DEBUG
	print "Creating master alignment...Parsing {} homologs...".format(str(count))
	for o in orthos:
		count -= 1
		present = []
		for line in open(os.path.join(outdir,"hmms",o+".hmm")):
			if line.startswith("LENG"):
				length = int(line.rstrip().split()[1])
				total_leng += length ###DEBUG
				break
		for line in open(os.path.join(outdir,"ortho_align",o+".sto")):
			if line.startswith("#") or line.startswith("//"):
				continue
			else:
				vals = line.rstrip().split()
				if len(vals) < 1:
					continue
				elif vals[0] in align_data:
					align_data[vals[0]].append(vals[1].translate(None,string.ascii_lowercase).replace(".",""))
					if vals[0] not in present:
						present.append(vals[0])
				else:
					align_data[vals[0]] = [vals[1].translate(None,string.ascii_lowercase).replace(".","")]
					if vals[0] not in present:
						present.append(vals[0])
		for s in strains:
			if s not in present:
				align_data[s].append("-"*length)
			if len("".join(align_data[s])) != total_leng:
				print s, "is short!"
				print total_leng, len("".join(align_data[s]))
				print align_data[s]
				print o
				sys.exit()
		if count % 100 == 0:
			print "\t"+str(count), "remaining..."
		else:
			pass
	print "Done!"
	print "Writing alignment..."
	out = open(prefix+".faa",'w')
	for a in align_data:
		out.write(">{}\n{}\n".format(a,"".join(align_data[a]).upper().replace(".","-")))
	out.close()
	out = open(prefix+".orthos.txt",'w')
	[out.write("{}\n".format(orth)) for orth in orthos]
	out.close()
	return

def get_strains():
	strains = [line.rstrip() for line in open(os.path.join(outdir,"strainlist.txt"))]
	[strains.append(s) for s in [line.rstrip() for line in open(os.path.join(outdir,"prop_strainlist.txt"))]]
	return strains

def index_hmms():
	print "Indexing all_groups.hmm..."
	cmds = "hmmfetch --index {}".format(os.path.join(outdir,"all_groups.hmm"))
	proc = subprocess.Popen(cmds.split())
	proc.wait()
	return

def main():
	args = parse_args()
	prefix = os.path.abspath(args.prefix)
	global outdir
	outdir = os.path.abspath(args.outdir)

	pp.createdirs(outdir,["ortho_align","concat","hmms"])
	if args.strains:
		strains = [line.rstrip() for line in open(os.path.abspath(args.strains),'r')]
	else:
		strains = get_strains()

	if args.orthos:
		orthos = [line.rstrip() for line in open(os.path.abspath(args.orthos),'r')]
	else:
		if args.threshold:
			orthos = parse_threshold_matrix(args.threshold,strains)
		else:
			orthos = parse_matrix(strains)

	if args.cpus:
		cpus = args.cpus
	else:
		cpus = mp.cpu_count()

	index_hmms()
	extract_hmms(orthos)

	concat_orthos(orthos,strains,cpus)
	align_orthos(orthos,cpus)
	create_master_alignment(orthos,strains,prefix)
	if args.clean:
		pp.cleanup(os.path.join(outdir,"ortho_align"))
		pp.cleanup(os.path.join(outdir,"concat"))


if __name__ == '__main__':
	main()