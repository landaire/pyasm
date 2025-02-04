from dis import opmap
from types import CodeType
from StringIO import StringIO
import dispy

def exec_input(consts=None, names=None, varnames=None, freevars=None, cellvars=None):
	exec compile_input(consts=consts, names=names, varnames=varnames, freevars=freevars, cellvars=cellvars)

def compile_input(consts=None, names=None, varnames=None, freevars=None, cellvars=None):
	out = StringIO()
	out.write('code\n')
	if consts:
		dispy.write_list(out, consts, 1, 'consts')
	if names:
		dispy.write_list(out, names, 1, 'names')
	if varnames:
		dispy.write_list(out, varnames, 1, 'varnames')
	if freevars:
		dispy.write_list(out, freevars, 1, 'freevars')
	if cellvars:
		dispy.write_list(out, consts, 1, 'cellvars')
	while 1:
		print('pyasm>'),
		line = raw_input()
		if line.strip() == '':
			break;
		out.write(line + '\n')
	out.write('end\n')
	out.seek(0)
	return read_object(out)

def parse_file(filename):
	f = open(filename, 'r')
	o = read_object(f)
	f.close()
	return o

def parse_int(i):
	negate = False
	value = None
	if i[0] == '-':
		negate = True
		i = i[1:]
	if i[:2] == '0x':
		value = int(i, 16)
	elif i[:2] == '0b':
		value = int(i, 2)
	else:
		value = int(i)
	if negate:
		return -value
	return value

def read_line(f):
	return f.readline().strip()

# l is typically the next line in the stream, but can be overridden in some circumstances
def read_object(f, l=None):
	if l == None:
		l = read_line(f)
	if l.split()[0] == 'string':
		return read_string(l)
	elif l.split()[0] == 'int' or l.split()[0] == 'int64':
		return read_int(l)
	elif l.split()[0] == 'float':
		return read_float(l)
	elif l.split()[0] == 'code':
		return read_code(f)
	elif l.split()[0] == 'none':
		return read_none(l)
	elif l.split()[0] == 'list':
		return read_list(f, parse_int(l.split()[1]))
	elif l.split()[0] == 'tuple':
		return tuple(read_list(f, parse_int(l.split()[1])))
	elif l.split()[0] == 'dict':
		return read_dict(f, parse_int(l.split()[1]))
	elif l.split()[0] == 'include':
		return parse_file(read_string(l) + '.pyasm')

def read_dict(f, count):
	r = {}
	for i in range(count):
		r[read_object(f)] = read_object(f)
	return r

def is_number(s):
	if s >= '0' and s <= '9':
		return True
	return False

def read_list(f, count):
	r = [None] * count
	index = 0
	l = read_line(f)
	while l != 'end':
		if is_number(l.split()[0][0]) and l.split()[1] != '*':
			index = parse_int(l.split()[0])
			l = l.split(' ', 1)[1]
			r[index] = read_object(f, l)
			index += 1
		elif is_number(l.split()[0][0]):
			count = parse_int(l.split()[0])
			l = l.split(' ', 2)[2]
			obj = read_object(f, l)
			for i in range(count):
				r[index] = obj
				index += 1
		else:
			r[index] = read_object(f, l)
			index += 1
		l = read_line(f)
	return r

def read_string(l):
	s = l.split('"', 1)[1]
	end_index = 0
	escaped = False
	for i in range(len(s)):
		if escaped:
			continue
		if s[i] == '"':
			end_index = i
			break
		if s[i] == '\\':
			escaped = True

	return s[:i].decode("string-escape")

def read_int(l):
	return parse_int(l.split()[1])

def read_float(l):
	return float(l.split()[1])

def read_none(l):
	return None

def process_labels(f):
	labels = {}
	l = read_line(f).split('#')[0].strip()
	pos = 0

	while l != 'end':
		count = 1
		instruction_len = 1
		if l[-1] == ':': # check for a : to see if the current line is a label
			labels[l[:-1]] = pos
			count = 0 # not an instruction
		elif len(l.split()) > 2:
			if l.split()[1] == '*':
				count = parse_int(l.split()[0])
				l = l.split(' ', 2)[-1]

		elif len(l.split()) == 2:
			instruction_len = 3
		pos += count * instruction_len

		l = read_line(f)

	return labels

def assemble_instructions(f):
	# save the position at the start of the instructions so we can restore it after we process labels
	start_pos = f.tell()
	labels = process_labels(f)

	f.seek(start_pos)
	l = read_line(f).split('#')[0].strip()
	sio = StringIO()
	while l != 'end':
		count = 1
		if l[-1] == ':': # skip labels
			count = 0
		elif len(l.split()) > 2:
			if l.split()[1] == '*':
				count = parse_int(l.split()[0])
				l = l.split(' ', 2)[-1]
		for i in range(count):
			if is_number(l[0]):
				sio.seek(parse_int(l.split()[0]))
				l = l.split(' ', 1)[1]
			line = l.split()
			if line[0].startswith('<'):
				print("invalid instr")
				print(line)
				# Replace this instruction with a nop
				print("nop")
				sio.write(chr(opmap['NOP']))
				# Replace the byte width of each arg with a nop
				if len(line) == 2:
					for arg in line[1].split(' '):
						if arg[0].isdigit(): # oparg is an immediate value
							oparg = parse_int(arg)
							while oparg != 0:
								print('nop')
								sio.write(chr(opmap['NOP']))
								oparg = oparg >> 8
						else:
							print(arg)
							raise Exception('handle non-digit args for nops')
				continue
			sio.write(chr(opmap[line[0]]))
			if len(line) == 2:
				if line[1][0].isdigit(): # oparg is an immediate value
					oparg = parse_int(line[1])
				else:
					oparg = labels[line[1]]

				sio.write(chr(oparg & 0xFF))
				sio.write(chr((oparg >> 8) & 0xFF))
		l = read_line(f).split('#')[0].strip()
	code = sio.getvalue()
	sio.close()
	return code

def read_code(f):
	arg_count = 0
	n_locals = 0
	stack_size = 0
	flags = 0
	first_line_no = 0
	filename = ''
	name = ''
	lnotab = ''
	consts = ()
	names = ()
	varnames = ()
	freevars = ()
	cellvars = ()
	code = ''
	l = read_line(f)
	while l != 'end':
		line = l.split()
		if line[0] == 'arg_count':
			arg_count = parse_int(line[1])
		elif line[0] == 'n_locals':
			n_locals = parse_int(line[1])
		elif line[0] == 'stack_size':
			stack_size = parse_int(line[1])
		elif line[0] == 'flags':
			flags = parse_int(line[1])
		elif line[0] == 'consts':
			consts = tuple(read_list(f, parse_int(line[1])))
		elif line[0] == 'names':
			names = tuple(read_list(f, parse_int(line[1])))
		elif line[0] == 'varnames':
			varnames = tuple(read_list(f, parse_int(line[1])))
		elif line[0] == 'freevars':
			freevars = tuple(read_list(f, parse_int(line[1])))
		elif line[0] == 'cellvars':
			cellvars = tuple(read_list(f, parse_int(line[1])))
		elif line[0] == 'instructions':
			code = assemble_instructions(f)
		elif line[0] == 'filename':
			filename = l.split('"')[1]
		elif line[0] == 'name':
			name = intern(l.split('"')[1])
		elif line[0] == 'lnotab':
			lnotab = l.split('"')[1].join("\"").decode('string-escape')
		elif line[0] == 'first_line_no':
			first_line_no = parse_int(line[1])
		l = read_line(f)
	return CodeType(arg_count, n_locals, stack_size, flags, code, consts, names, varnames, filename, name, first_line_no, lnotab, freevars, cellvars)

