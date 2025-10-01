import express, { Request, Response } from 'express';
import auth, { AuthRequest } from "../middleware/auth";
import ProjectModel, { Project } from '../models/Project';

const router = express.Router();


// @route   GET /projects
// @desc    Get all projects
// @access  Private
router.get('/', auth, async (req: AuthRequest, res: Response)  => {
    try {
        const projects = await ProjectModel.find().lean().exec();
        res.json(projects);
    } catch (err) {
        console.error(err);
        res.status(500).send('Server Error');
    }
});

// @route   GET /projects/:id
// @desc    Get a project by its ID
// @access  Private
router.get('/:id', auth, async (req: AuthRequest & {params: { id: string}}, res: Response) => {
    try {
        const project = await ProjectModel.findById(req.params.id).exec();
        if (!project) {
            return res.status(404).json({ msg: 'Project not found' });
        }
        res.json(project); // THE FIX: This now correctly uses the singular 'project'
    } catch (err) {
        console.error(err);
        res.status(500).send('Server Error');
    }
});

// @route   PUT /projects/:id
// @desc    Update a project's details (eg. calculator values)
// @access  Private
router.put('/:id', auth, async (req: AuthRequest& { params: { id: string } }, res: Response) => {
    try {
        const updatedProject = await ProjectModel.findByIdAndUpdate(
            req.params.id,
            req.body,
            { new: true }
        ).exec();
        if (!updatedProject) {
            return res.status(404).json({ msg: 'Project not found' });
        }
        res.json(updatedProject);
    } catch (err) {
        console.error(err);
        res.status(400).json({ msg: 'Error updating project' });
    }
});

//@route   POST /projects:id/phases
//@desc    Add a new phase to a project
//@access  Private
router.post('/:id/phases', auth, async (req, res)=> {
    try {
        const project = await ProjectModel.findById(req.params.id).exec();
        if (!project) {
            return res.status(404).json({ msg: "Project not Found" });
        }

// New Phase Object
// Data was sent by the client to the server and the data in the body of th POST request is accessed using req.body
        const newPhase = {
            name: req.body.name,
            startDate: req.body.startDate,
            endDate: req.body.endDate,
            assignedTo: req.body.assignedTo,
            status: req.body.status ||'Scheduled'
        };

// 'Phases in the database model is an array, so we use 'unshift()' to add the new phase to the beginning of the array
        project.phases.unshift(newPhase as any);

// Permanently save the changes to the database using 'save()' after modifying the 'project' object in memory
         await project.save();

// Send a success msg as well as the entire updatted project back to the front end

        res.json(project);
    } catch (err: any) {
        console.error(err.message);
        res.status(500).send('Server Error');
    }



});



export default router;