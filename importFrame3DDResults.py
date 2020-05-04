#

__title__ = "FreeCAD Frame3DD library"
__author__ = "John Wang based on importCcxFrdResults.py" 

## @package importFrame3DDResults
#  \ingroup FEM
#  \brief FreeCAD Frame3DD Reader for FEM workbench

import FreeCAD
from FreeCAD import Console
import os
import Fem

class Node:
    def __init__(self, id , x,y,z):
        self.x = x
        self.y = y
        self.z = z
        self.id = str(id)

# elmnt n1     n2    Ax     Asy     Asz     Jx     Iy     Iz     E     G     roll  density
class Member:
    def __init__(self, id , n1,n2):
        self.n1 = n1
        self.n2 = n2
        self.id = str(id)

# ********* generic FreeCAD import and export methods *********
if open.__module__ == "__builtin__":
    # because we'll redefine open below (Python2)
    pyopen = open
elif open.__module__ == "io":
    # because we'll redefine open below (Python3)
    pyopen = open


def open(filename):
    "called when freecad opens a file"
    docname = os.path.splitext(os.path.basename(filename))[0]
    insert(filename, docname)


def insert(
    filename,
    docname
):
    "called when freecad wants to import a file"
    try:
        doc = FreeCAD.getDocument(docname)
    except NameError:
        doc = FreeCAD.newDocument(docname)
    FreeCAD.ActiveDocument = doc
    importFrame3DD(filename)
	
# ********* module specific methods *********
def importFrame3DD(
    filename,
    analysis=None,
    result_name_prefix=""
):
    from . import importToolsFem
    #from . import Fem.feminout.importToolsFem
    import ObjectsFem

	#import result mesh only
    Console.PrintMessage(
        "Read Frame3DD results from Frame3DD file: {}\n"
        .format(filename)
    )
    Frame3DD_file = pyopen(filename, "r")
    nodes = {}

    elem = -1
    elemType = 0
	
    nDisp=0
	
    numNode =  0
    numFixedNode =  0
    numMember =  0
    numLC =  0
	
    isDebug=0
		
    NodeList = {}
    MemberList = {}                                  
	
    tline=[]
    for line in Frame3DD_file:
        tline.append(line.strip())
		
    for i in range(len(tline)):
	
        #Console.PrintError(tline[i])
        tStrNode="In 2D problems the Y-axis is vertical.  In 3D problems the Z-axis is vertical."	
        if tline[i].strip() == tStrNode:
            #Console.PrintError("FEM: nodes found.\n")
			
            i=i+1
            i=i+1
            data = tline[i].split()
            #12 NODES             12 FIXED NODES       21 FRAME ELEMENTS   2 LOAD CASES   
            numNode =  int(data[0])
            numFixedNode =  int(data[2])
            numMember =  int(data[5])
            numLC =  int(data[8])
	
            i=i+1 # = fp.readline().strip()
            i=i+1 # = fp.readline().strip()
            i=i+1 # = fp.readline().strip()
			
            #print ("")			
            #print ("numNode: "+str(numNode))
            for id in range(numNode): # node
                #1       0.000000       0.000000       0.000000    0.000   1  1  1  1  1  0
                i=i+1
                #print (tline[i])
                dataNode = tline[i].split()
			
                elem = int(dataNode[0])
                nodes_x = float(dataNode[1])
                nodes_y = float(dataNode[2])
                nodes_z = float(dataNode[3])
                nodes[elem] = FreeCAD.Vector(nodes_x, nodes_y, nodes_z)
                NodeList[id] =  Node(str(id+1), nodes_x, nodes_y, nodes_z )

            i=i+1
            i=i+1
			
            #print ("")			
            #print ("numMember: "+str(numMember))
            for id in range(numMember): # Member
                i=i+1
                #print (tline[i])
                dataNode = tline[i].split()
                elem = int(dataNode[0])
                nd1 = int(dataNode[1])
                nd2 = int(dataNode[2])
                MemberList[id] =  Member(str(id+1) ,nd1, nd2)  

            #print ("")			
            #print ("numFixedNode: "+str(numFixedNode))
            #print ("numLC: "+str(numLC))
		
            femmesh = Fem.FemMesh()
            # nodes
            #print ("Add nodes")
            for id in NodeList: # node
                #femmesh.addNode(NodeList[id].x,NodeList[id].y,NodeList[id].z, int(id)+1 )
                femmesh.addNode(NodeList[id].x,NodeList[id].y,NodeList[id].z, int(id)+1 )
			
            # elements
            for id in MemberList:
                n1 = MemberList[id].n1
                n2 = MemberList[id].n2
                femmesh.addEdge([int(n1), int(n2)], int(id)+1)
				
			
			
    # close Frame3DD file if loop over all lines is finished
    Frame3DD_file.close()

    if not nodes:
        Console.PrintError("FEM: No nodes found in Frame3DD file.\n")
    else:	
	
        #Console.PrintError(tline[i])
        result_mesh_object = None
        #mesh = importToolsFem.make_femmesh(m)
        result_mesh_object = ObjectsFem.makeMeshResult(
            FreeCAD.ActiveDocument,
            "ResultMesh"
        )
        result_mesh_object.FemMesh = femmesh
        res_mesh_is_compacted = False
        nodenumbers_for_compacted_mesh = []
		
		
		

        #import result 
        mm = read_Frame3DD_result(filename)
		
        number_of_increments = len(mm["Results"])
        Console.PrintLog(
            "Increments: " + str(number_of_increments) + "\n"
        )
		
        if len(mm["Results"]) > 0:
		
            res_obj=[]		
            iLC=0
            iModal=0
            results_name="Elastic"
				
            for result_set in mm["Results"]:
                if (iLC<numLC):				
                    results_name="Elastic"
                    res_obj.append(ObjectsFem.makeResultMechanical(FreeCAD.ActiveDocument, results_name+str(iLC)))
                else:
                    results_name="Modal"
                    res_obj.append(ObjectsFem.makeResultMechanical(FreeCAD.ActiveDocument, results_name+str(iModal)))
                    iModal+=1
            				
                res_obj[iLC].Mesh = result_mesh_object
                res_obj[iLC] = importToolsFem.fill_femresult_mechanical(res_obj[iLC], result_set)
                if analysis:
                    analysis.addObject(res_obj[iLC])

                # complementary result object calculations
                import femresult.resulttools as restools
                import femtools.femutils as femutils
                if not res_obj[iLC].MassFlowRate:
                    if res_mesh_is_compacted is False:
                        # first result set, compact FemMesh and NodeNumbers
                        res_obj[iLC] = restools.compact_result(res_obj[iLC])
                        res_mesh_is_compacted = True
                        nodenumbers_for_compacted_mesh = res_obj[iLC].NodeNumbers
                    else:
                        # all other result sets, do not compact FemMesh, only set NodeNumbers
                        res_obj[iLC].NodeNumbers = nodenumbers_for_compacted_mesh

                # fill DisplacementLengths
                res_obj[iLC] = restools.add_disp_apps(res_obj[iLC])
                # fill StressValues
                res_obj[iLC] = restools.add_von_mises(res_obj[iLC])
                if res_obj[iLC].getParentGroup():
                    has_reinforced_mat = False
                    for obj in res_obj[iLC].getParentGroup().Group:
                        if obj.isDerivedFrom("App::MaterialObjectPython") \
                                and femutils.is_of_type(obj, "Fem::MaterialReinforced"):
                            has_reinforced_mat = True
                            restools.add_principal_stress_reinforced(res_obj[iLC])
                            break
                    if has_reinforced_mat is False:
                        # fill PrincipalMax, PrincipalMed, PrincipalMin, MaxShear
                        res_obj[iLC] = restools.add_principal_stress_std(res_obj[iLC])
                else:
                    # if a pure Frame3DD file was opened no analysis and thus no parent group
                    # fill PrincipalMax, PrincipalMed, PrincipalMin, MaxShear
                    res_obj[iLC] = restools.add_principal_stress_std(res_obj[iLC])
                # fill Stats
                res_obj[iLC] = restools.fill_femresult_stats(res_obj[iLC])
				
                iLC+=1

            return res_obj


        else:
            error_message = (
                "We have nodes only.\n"
            )
            Console.PrintMessage(error_message)
            if analysis:
                analysis.addObject(result_mesh_object)

        if FreeCAD.GuiUp:
            if analysis:
                import FemGui
                FemGui.setActiveAnalysis(analysis)
            FreeCAD.ActiveDocument.recompute()



# read a Frame3DD result file and extract
# the displacement vectors and stress values.
def read_Frame3DD_result(
    Frame3DD_input
):
    Console.PrintMessage(
        "Read Frame3DD results from Frame3DD file: {}\n"
        .format(Frame3DD_input)
    )
    Frame3DD_file = pyopen(Frame3DD_input, "r")
    nodes = {}
    elements_hexa8 = {}
    elements_penta6 = {}
    elements_tetra4 = {}
    elements_tetra10 = {}
    elements_penta15 = {}
    elements_hexa20 = {}
    elements_tria3 = {}
    elements_tria6 = {}
    elements_quad4 = {}
    elements_quad8 = {}
    elements_seg2 = {}
    elements_seg3 = {}
    results = []
    mode_results = {}
    #mode_results["number"] = float("NaN")
    #mode_results["time"] = float("NaN")
    mode_disp = {}
    mode_stress = {}
    mode_strain = {}
    mode_peeq = {}
    mode_temp = {}
    mode_massflow = {}
    mode_networkpressure = {}

    nodes_found = False
    elements_found = False
    mode_time_found = False
    mode_disp_found = False
    mode_stress_found = False
    mode_strain_found = False
    mode_peeq_found = False
    mode_temp_found = False
    mode_massflow_found = False
    mode_networkpressure_found = False
    end_of_section_found = False
    end_of_Frame3DD_data_found = False
    input_continues = False
    mode_eigen_changed = False
    mode_time_changed = False

    eigenmode = 0
    eigentemp = 0
    elem = -1
    elemType = 0
    timestep = 0
    timetemp = 0
	
    nDisp=0
    mDisp=0
	
    numNode =  0
    numFixedNode =  0
    numMember =  0
    numLC =  0
	
    isDebug=0
    iFilled=[]
	
    tline=[]
    for line in Frame3DD_file:
        tline.append(line.strip())
 
    isElastic=0
    isModal=0
    for i in range(len(tline)):
	
        tStrNode="In 2D problems the Y-axis is vertical.  In 3D problems the Z-axis is vertical."	
        if tline[i].strip() == tStrNode:
            #Console.PrintError("FEM: nodes found.\n")
			
            i=i+1
            i=i+1
            data = tline[i].split()
            #12 NODES             12 FIXED NODES       21 FRAME ELEMENTS   2 LOAD CASES   
            numNode =  int(data[0])
            numFixedNode =  int(data[2])
            numMember =  int(data[5])
            numLC =  int(data[8])
			
            for id in range(numNode): # node
                iFilled.append(0)
			
        tStrDis="E L A S T I C   S T I F F N E S S   A N A L Y S I S   via  L D L'  decomposition"
        if tline[i].strip() == tStrDis:
            #Console.PrintError("FEM: displacement found.\n")
            isElastic=1
			
        if (isElastic==1 and isModal==0):
            tStrDis="Node    X-dsp       Y-dsp       Z-dsp       X-rot       Y-rot       Z-rot"
            if tline[i].strip() == tStrDis:
                #Console.PrintError("FEM: displacement found.\n")
			
                print ("")			
                print ("Displacement"+str(nDisp))	
				
                for id in range(numNode): # node
                    iFilled[id]=0
				
                for id in range(numNode): # node
                    #Node    X-dsp       Y-dsp       Z-dsp       X-rot       Y-rot       Z-rot
                    #1    0.0         0.0         0.0         0.0         0.0        -0.001254
                    i=i+1
                    #print (tline[i])
                    dataNode = tline[i].split()
                    #print (dataNode[0]+" "+str(numNode))
                    if (dataNode[0].isdigit()):
                        elem = int(dataNode[0])
                        iFilled[elem-1] = 1
                        mode_disp_x = float(dataNode[1])
                        mode_disp_y = float(dataNode[2])
                        mode_disp_z = float(dataNode[3])
                        mode_disp[elem] = FreeCAD.Vector(mode_disp_x, mode_disp_y, mode_disp_z)
                    else:
                        break
				
                for id in range(numNode): # node
                    if (iFilled[id] == 0):
                        mode_disp[id+1] = FreeCAD.Vector(0., 0., 0.)
                    #print (str(id)+" "+str(iFilled[id]))	
				
                #mode_results["disp"+str(nDisp)] = mode_disp
                mode_results["disp"] = mode_disp
                mode_disp = {}

                nDisp+=1	
				
                # append mode_results to results and reset mode_result
                results.append(mode_results)
                mode_results = {}

				
				
				
		#mode shapes	
		
        tStrDis="M O D A L   A N A L Y S I S   R E S U L T S"
        if tline[i].strip() == tStrDis:
            #Console.PrintError("FEM: displacement found.\n")
            isModal=1
			
        if (isModal==1):
            tStrDis="Node    X-dsp       Y-dsp       Z-dsp       X-rot       Y-rot       Z-rot"
            if tline[i].strip() == tStrDis:
                #Console.PrintError("FEM: displacement found.\n")
			
                print ("")			
                print ("Modal Displacement"+str(mDisp))			
			
                for id in range(numNode): # node
                    iFilled[id]=0
				
                for id in range(numNode): # node
                    #Node    X-dsp       Y-dsp       Z-dsp       X-rot       Y-rot       Z-rot
                    #1    0.0         0.0         0.0         0.0         0.0        -0.001254
					#" %11.3e"
                    #1 -1.#IOe+000 -1.#IOe+000 -1.#IOe+000 -1.#IOe+000 -1.#IOe+000 -1.#IOe+000
                    i=i+1
                    #print (tline[i])
                    dataNode = tline[i].split()
                    #print (dataNode[0]+" "+str(numNode))
                    if (dataNode[0].isdigit()):
                        elem = int(dataNode[0])
                        iFilled[elem-1] = 1
                        mode_disp_x = float(dataNode[1])
                        mode_disp_y = float(dataNode[2])
                        mode_disp_z = float(dataNode[3])
                        mode_disp[elem] = FreeCAD.Vector(mode_disp_x, mode_disp_y, mode_disp_z)
                    else:
                        break
		
                for id in range(numNode): # node
                    if (iFilled[id] == 0):
                        mode_disp[id+1] = FreeCAD.Vector(0., 0., 0.)
                    #print (str(id)+" "+str(iFilled[id]))	
				
                #mode_results["disp"+str(nDisp)] = mode_disp
                mode_results["disp"] = mode_disp
                mode_disp = {}

                mDisp+=1	
				
                # append mode_results to results and reset mode_result
                results.append(mode_results)
                mode_results = {}
			

    # https://forum.freecadweb.org/viewtopic.php?f=18&t=32649&start=10#p274686
    #mode_results["number"] = float("NaN")
    #mode_results["time"] = float("NaN")

    # here we are in the indent of loop for every line in Frame3DD file
    # do not add a print here :-)

    # close Frame3DD file if loop over all lines is finished
    Frame3DD_file.close()

    return {
        "Nodes": nodes,
        "Seg2Elem": elements_seg2,
        "Seg3Elem": elements_seg3,
        "Tria3Elem": elements_tria3,
        "Tria6Elem": elements_tria6,
        "Quad4Elem": elements_quad4,
        "Quad8Elem": elements_quad8,
        "Tetra4Elem": elements_tetra4,
        "Tetra10Elem": elements_tetra10,
        "Hexa8Elem": elements_hexa8,
        "Hexa20Elem": elements_hexa20,
        "Penta6Elem": elements_penta6,
        "Penta15Elem": elements_penta15,
        "Results": results
    }
	
