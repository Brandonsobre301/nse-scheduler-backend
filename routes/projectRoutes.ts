import express, { Request, Response, NextFunction } from 'express';
import auth, { AuthRequest } from "../middleware/auth";
// lightweight requireRole middleware implemented inline to avoid missing module
const requireRole = (...roles: string[]) => {
    return (req: AuthRequest, res: Response, next: NextFunction) => {
        // If auth middleware did not attach a user, deny access
        if (!req.user || !('role' in req.user)) {
            return res.status(403).json({ msg: 'Access denied' });
        }
        const userRole = (req.user as any).role;
        if (!roles.includes(userRole)) {
            return res.status(403).json({ msg: 'Access denied' });
        }
        next();
    };
};
import ProjectModel, { Project } from '../models/Project';

const router = express.Router();

// @route   GET /projects
// @desc    Get all projects (anyone authenticated can view)
// @access  Private
router.get('/', auth, async (req: AuthRequest, res: Response) => {
    try {
        const projects = await ProjectModel.find().lean().exec();
        res.json(projects);
    } catch (err) {
        console.error(err);
        res.status(500).send('Server Error');
    }
});

// @route   GET /projects/:id
// @desc    Get a project by ID (anyone authenticated can view)
// @access  Private
router.get('/:id', auth, async (req: AuthRequest & {params: { id: string}}, res: Response) => {
    try {
        const project = await ProjectModel.findById(req.params.id).exec();
        if (!project) {
            return res.status(404).json({ msg: 'Project not found' });
        }
        res.json(project);
    } catch (err) {
        console.error(err);
        res.status(500).send('Server Error');
    }
});

// @route   POST /projects
// @desc    Create a new project (managers and admins only)
// @access  Private (manager, admin)
router.post('/', auth, requireRole('admin', 'manager'), async (req: AuthRequest, res: Response) => {
    try {
        let { name, projectNumber, manager, status, deadline, totalManHours, desiredManpower, efficiency } = req.body;

        // Trim input fields
        name = (name || '').trim();
        projectNumber
        manager = (manager || '').trim();

        if (!name) {
            return res.status(400).json({ msg: 'Project name is required' });
        }
        if (!projectNumber) {
            return res.status(400).json({ msg: 'Project number is required' });
        }
        if (!manager) {
            return res.status(400).json({ msg: 'Project manager is required' });
        }

        const existingProject = await ProjectModel.findOne({ projectNumber }).exec();
        if (existingProject) {
            return res.status(400).json({ msg: 'Project number must be unique' });
        }

        const newProject = new ProjectModel({
            name,
            projectNumber,
            manager,
            status: status || 'Active',
            progress: 0,
            deadline: deadline ? new Date(deadline) : undefined,
            team: [],
            phases: [],
            totalManHours: totalManHours || 0,
            desiredManpower: desiredManpower || 1,
            efficiency: efficiency || 0.8,
            targetDurationWeeks: 0
        });
        const savedProject = await newProject.save();

        res.status(201).json({
            msg: 'Project created successfully',
            project: savedProject
        });
    } catch (err) {
        console.error(err);
        res.status(500).send('Server Error');
    }
});

// @route   PUT /projects/:id
// @desc    Update a project (managers and admins only)
// @access  Private (manager, admin)
router.put('/:id', auth, requireRole('admin', 'manager'), async (req: AuthRequest & { params: { id: string } }, res: Response) => {
    try {
        const { id } = req.params;
        
        if (!id || id === 'undefined' || !id.match(/^[0-9a-fA-F]{24}$/)) {
            return res.status(400).json({ msg: 'Invalid project ID format' });
        }

        console.log('Updating project ID:', id);
        console.log('Update data:', req.body);

        const updatedProject = await ProjectModel.findByIdAndUpdate(
            id,
            req.body,
            { new: true, runValidators: true }
        ).lean().exec();

        if (!updatedProject) {
            return res.status(404).json({ msg: 'Project not found' });
        }

        const response = {
            ...updatedProject,
            _id: updatedProject._id.toString()
        };

        console.log('Returning project with _id:', response._id);
        res.json(response);
    } catch (err) {
        console.error('Update error:', err);
        res.status(400).json({ msg: 'Error updating project' });
    }
});

// @route   POST /projects/:id/phases
// @desc    Add a new phase (managers and admins only)
// @access  Private (manager, admin)
router.post('/:id/phases', auth, requireRole('admin', 'manager'), async (req, res) => {
    try {
        const project = await ProjectModel.findById(req.params.id).exec();
        if (!project) {
            return res.status(404).json({ msg: "Project not Found" });
        }

        const newPhase = {
            name: req.body.name,
            startDate: req.body.startDate,
            endDate: req.body.endDate,
            assignedTo: req.body.assignedTo,
            status: req.body.status || 'Scheduled'
        };

        project.phases.unshift(newPhase as any);
        await project.save();

        res.json(project);
    } catch (err: any) {
        console.error(err.message);
        res.status(500).send('Server Error');
    }
});

// @route   DELETE /projects/:id
// @desc    Delete a project (admins only)
// @access  Private (admin)
router.delete('/:id', auth, requireRole('admin'), async (req: AuthRequest & { params: { id: string } }, res: Response) => {
    try {
        const { id } = req.params;

        if (!id || id === 'undefined' || !id.match(/^[0-9a-fA-F]{24}$/)) {
            return res.status(400).json({ msg: 'Invalid project ID format' });
        }
        const deletedProject = await ProjectModel.findByIdAndDelete(id).exec();
        if (!deletedProject) {
            return res.status(404).json({ msg: 'Project not found' });
        }
        res.json({ msg: 'Project deleted successfully' });
    } catch (err) {
        console.error(err);
        res.status(500).send('Server Error');
    }
});
export default router;